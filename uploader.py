import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
import pickle

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE  = os.path.join(os.path.dirname(__file__), "client_secrets.json")
TOKENS_DIR           = os.path.join(os.path.dirname(__file__), "tokens")
SCOPES               = ["https://www.googleapis.com/auth/youtube"]
RESTORE_CHANNEL_NAME = "restore"   # matched case-insensitively

# ── Channel 1 defaults ────────────────────────────────────────────────────────
CH1_TITLE       = "quote of the day"
CH1_DESCRIPTION = """Subscribe for daily quotes that understand you.
#quotes #emotionalquotes #relatablequotes #deepquotes #sadquotes #lovequotes #lifequotes #inspirationalquotes #motivationalquotes #viralquotes #quoteshorts #youtubeshortsquotes #tiktokquotes #reelsquotes #dailyquotes #personalquotes #healingquotes #overthinkingquotes #lonelinessquotes #movingonquotes #heartbreakquotes #relationshipquotes #innerthoughts #unspokenfeelings #latenightthoughts #darktruthquotes #selflovequotes #mindsetquotes #realtalkquotes #aestheticquotes #shortquotes #powerfulquotes #facelesschannel #shareablequotes #scrollstoppingquotes"""
CH1_TAGS        = [
    "quotes","emotional quotes","relatable quotes","deep quotes","sad quotes",
    "love quotes","life quotes","inspirational quotes","motivational quotes",
    "viral quotes","quote shorts","daily quotes","personal quotes",
    "healing quotes","overthinking quotes","loneliness quotes","moving on quotes",
    "heartbreak quotes","relationship quotes","inner thoughts","unspoken feelings",
    "late night thoughts","self love quotes","mindset quotes","real talk quotes",
    "powerful quotes","shareable quotes"
]

# ── Channel 2 (Restore) defaults ──────────────────────────────────────────────
CH2_DESC_PREFIX = """Credits to the owner
#Lyrics #SongLyrics #LyricsVideo #LyricVideo #MusicLyrics #LyricsOfTheDay #LyricEdit #LyricsEdit #ViralLyrics #SongLyricsVideo #MusicVideo #TrendingLyrics #LyricsMatter #BestLyrics #LyricQuotes #SadLyrics #LoveLyrics #YouTubeLyrics #LyricsShorts #NewLyrics #classics"""
CH2_TAGS        = [
    "Lyrics","Song Lyrics","Lyrics Video","Lyric Video","Music Lyrics",
    "Lyrics Of The Day","Lyric Edit","Lyrics Edit","Viral Lyrics",
    "Song Lyrics Video","Music Video","Trending Lyrics","Lyrics Matter",
    "Best Lyrics","Lyric Quotes","Sad Lyrics","Love Lyrics",
    "YouTube Lyrics","Lyrics Shorts","New Lyrics","classics"
]

# ── Colors / Fonts ─────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
SURFACE  = "#16213e"
SURFACE2 = "#0d0d1a"
BORDER   = "#0f3460"
ACCENT   = "#e94560"
ACCENT2  = "#c73652"
FG       = "#e0e0e0"
FG_MUTED = "#888888"
FG_GREEN = "#7fcc7f"
FONT     = ("Consolas", 10)
FONT_SM  = ("Consolas", 9)
FONT_XS  = ("Consolas", 8)
FONT_LG  = ("Consolas", 11, "bold")
FONT_HDR = ("Consolas", 15, "bold")

# ── Auth helpers ──────────────────────────────────────────────────────────────
os.makedirs(TOKENS_DIR, exist_ok=True)

def _next_token_path():
    i = 1
    while True:
        p = os.path.join(TOKENS_DIR, f"token_{i}.pickle")
        if not os.path.exists(p):
            return p
        i += 1

def _all_token_paths():
    if not os.path.isdir(TOKENS_DIR):
        return []
    return sorted(
        os.path.join(TOKENS_DIR, f)
        for f in os.listdir(TOKENS_DIR)
        if f.startswith("token_") and f.endswith(".pickle")
    )

def _load_service(token_path):
    with open(token_path, "rb") as fh:
        creds = pickle.load(fh)
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def auth_new_account():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError("client_secrets.json not found. Place it next to uploader.py")
    flow  = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    token_path = _next_token_path()
    with open(token_path, "wb") as fh:
        pickle.dump(creds, fh)
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def fetch_channels(service):
    channels = []
    req = service.channels().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        resp = req.execute()
        for item in resp.get("items", []):
            channels.append((item["snippet"]["title"], item["id"], service))
        req = service.channels().list_next(req, resp)
    return channels

def load_all_saved_channels():
    all_ch = []
    for path in _all_token_paths():
        try:
            all_ch.extend(fetch_channels(_load_service(path)))
        except Exception:
            pass
    return all_ch


# ── Upload ────────────────────────────────────────────────────────────────────
def upload_video(service, file_path, channel_id, title, description, tags,
                 progress_cb, done_cb, error_cb, thumb_path=None):
    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "22",
            "channelId":   channel_id,
        },
        "status": {"privacyStatus": "private"},
    }
    media   = MediaFileUpload(file_path, chunksize=256 * 1024, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress_cb(int(status.progress() * 100))

        video_id = response.get("id", "unknown")

        # ── Thumbnail upload (optional) ───────────────────────────────────────
        if thumb_path and os.path.isfile(thumb_path) and video_id != "unknown":
            try:
                service.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumb_path)
                ).execute()
            except googleapiclient.errors.HttpError as te:
                # Non-fatal: video already uploaded; surface the warning via done_cb
                done_cb(video_id, thumb_warning=str(te))
                return

        done_cb(video_id)

    except googleapiclient.errors.HttpError as e:
        error_cb(str(e))
    except Exception as e:
        error_cb(str(e))


# ── Channel Tab Panel ─────────────────────────────────────────────────────────
class ChannelPanel(tk.Frame):
    """One panel per channel, shown when its tab is active."""

    def __init__(self, parent, channel_name, channel_id, service, app, **kw):
        super().__init__(parent, bg=BG, **kw)
        self.channel_name = channel_name
        self.channel_id   = channel_id
        self.service      = service
        self.app          = app
        self.is_restore   = channel_name.strip().lower() == RESTORE_CHANNEL_NAME

        self._file_path   = tk.StringVar()
        self._lyrics_path = tk.StringVar()
        self._thumb_path  = tk.StringVar()
        self._progress    = tk.IntVar(value=0)

        self._build()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lf(self, label):
        """Return a styled LabelFrame."""
        return tk.LabelFrame(self, text=f" {label} ", font=FONT_XS,
                             bg=SURFACE, fg=FG_MUTED, bd=1, relief="flat",
                             padx=10, pady=8)

    def _browse_row(self, parent, label_var, placeholder, command):
        """Reusable browse row: clickable label + Browse button."""
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", pady=(4, 0))
        lbl = tk.Label(row, textvariable=label_var,
                       text=placeholder, font=FONT_SM,
                       bg=SURFACE2, fg=FG_MUTED, anchor="w", padx=8,
                       relief="flat", bd=0,
                       highlightthickness=1, highlightbackground=BORDER,
                       cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True, ipady=6)
        lbl.bind("<Button-1>", lambda e: command())
        tk.Button(row, text="Browse", font=FONT_SM,
                  bg=BORDER, fg=FG, activebackground="#1a3a6e",
                  relief="flat", bd=0, padx=12, cursor="hand2",
                  command=command).pack(side="left", padx=(6, 0), ipady=6)
        return lbl

    # ── build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        # ── Video file section ────────────────────────────────────────────────
        vf = self._lf("Video File")
        vf.pack(fill="x", padx=16, pady=(14, 8))
        self._file_lbl = self._browse_row(vf, self._file_path,
                                          "No file selected", self._browse_video)

        # ── Restore-only sections ─────────────────────────────────────────────
        if self.is_restore:
            lf = self._lf("Lyrics File (.txt)")
            lf.pack(fill="x", padx=16, pady=(0, 8))
            self._lyrics_lbl = self._browse_row(lf, self._lyrics_path,
                                                "No file selected", self._browse_lyrics)

            tf = self._lf("Thumbnail (.png)")
            tf.pack(fill="x", padx=16, pady=(0, 8))
            self._thumb_lbl = self._browse_row(tf, self._thumb_path,
                                               "No file selected", self._browse_thumb)

        # ── Progress bar ──────────────────────────────────────────────────────
        pf = tk.Frame(self, bg=BG)
        pf.pack(fill="x", padx=16, pady=(0, 2))
        self._pbar = ttk.Progressbar(pf, variable=self._progress, maximum=100,
                                     style="red.Horizontal.TProgressbar")
        self._pbar.pack(fill="x")
        self._pct_lbl = tk.Label(pf, text="", font=FONT_XS, bg=BG, fg=FG_MUTED)
        self._pct_lbl.pack(anchor="e")

        # ── Upload button ─────────────────────────────────────────────────────
        self._btn_upload = tk.Button(
            self, text="⬆  Upload as Private",
            font=FONT_LG,
            bg=ACCENT, fg="white", activebackground=ACCENT2,
            relief="flat", bd=0, cursor="hand2", padx=10, pady=10,
            command=self._on_upload)
        self._btn_upload.pack(fill="x", padx=16, pady=(6, 16))

    # ── browse callbacks ──────────────────────────────────────────────────────
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[("MP4 files", "*.mp4"),
                       ("All video files", "*.mp4 *.mov *.avi *.mkv")])
        if path:
            self._file_path.set(path)
            self._file_lbl.configure(fg=FG)
            self.app.log(f"Video selected: {os.path.basename(path)}")

    def _browse_lyrics(self):
        path = filedialog.askopenfilename(
            title="Select lyrics file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._lyrics_path.set(path)
            self._lyrics_lbl.configure(fg=FG)
            self.app.log(f"Lyrics selected: {os.path.basename(path)}")

    def _browse_thumb(self):
        path = filedialog.askopenfilename(
            title="Select thumbnail (.png)",
            filetypes=[("PNG files", "*.png")])
        if path:
            self._thumb_path.set(path)
            self._thumb_lbl.configure(fg=FG)
            self.app.log(f"Thumbnail selected: {os.path.basename(path)}")

    # ── upload ────────────────────────────────────────────────────────────────
    def _on_upload(self):
        file = self._file_path.get()
        if not file or not os.path.isfile(file):
            messagebox.showwarning("No file", "Please select a valid video file.")
            return

        if self.is_restore:
            title  = os.path.splitext(os.path.basename(file))[0]
            lpath  = self._lyrics_path.get()
            tpath  = self._thumb_path.get() or None
            if not lpath or not os.path.isfile(lpath):
                messagebox.showwarning("No lyrics", "Please select a .txt lyrics file.")
                return
            with open(lpath, "r", encoding="utf-8") as fh:
                lyrics = fh.read().strip()
            description = f"{CH2_DESC_PREFIX}\n\n{title}\n\n{lyrics}"
            tags        = CH2_TAGS
        else:
            title       = CH1_TITLE
            description = CH1_DESCRIPTION
            tags        = CH1_TAGS
            tpath       = None

        self._progress.set(0)
        self._pct_lbl.configure(text="0%")
        self._btn_upload.configure(state="disabled", text="Uploading…")
        self.app.log(f"\nStarting upload → {self.channel_name} : {os.path.basename(file)}")

        threading.Thread(
            target=upload_video,
            args=(self.service, file, self.channel_id, title, description, tags,
                  self._on_progress, self._on_done, self._on_error),
            kwargs={"thumb_path": tpath},
            daemon=True
        ).start()

    def _on_progress(self, pct):
        self.after(0, lambda: (
            self._progress.set(pct),
            self._pct_lbl.configure(text=f"{pct}%"),
            self.app.log(f"  {pct}%") if pct % 25 == 0 else None
        ))

    def _on_done(self, video_id, thumb_warning=None):
        def _update():
            self._progress.set(100)
            self._pct_lbl.configure(text="100%")
            self._btn_upload.configure(state="normal", text="⬆  Upload as Private")
            if thumb_warning:
                self.app.log(f"  ✔ Done — ID: {video_id}  ⚠ Thumbnail: {thumb_warning}")
                messagebox.showwarning(
                    "Done (thumbnail warning)",
                    f"Upload complete!\nVideo ID: {video_id}\n\nThumbnail failed:\n{thumb_warning}")
            else:
                self.app.log(f"  ✔ Done — ID: {video_id}")
                messagebox.showinfo("Done",
                    f"Upload complete!\nVideo ID: {video_id}\n\nStatus: Private")
        self.after(0, _update)

    def _on_error(self, msg):
        def _update():
            self._btn_upload.configure(state="normal", text="⬆  Upload as Private")
            self.app.log(f"  ✖ Error: {msg}")
            messagebox.showerror("Upload failed", msg)
        self.after(0, _update)


# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YT Uploader")
        self.geometry("600x620")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._channels = []   # (name, id, service)
        self._panels   = {}   # name -> ChannelPanel
        self._tab_btns = {}   # name -> tk.Button
        self._active   = None

        self._setup_styles()
        self._build_ui()
        threading.Thread(target=self._load_saved, daemon=True).start()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("red.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT,
                        bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT2,
                        thickness=8)

    def _build_ui(self):
        # ── Top accent bar ────────────────────────────────────────────────────
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(14, 0))

        tk.Label(header, text="YT UPLOADER", font=FONT_HDR,
                 bg=BG, fg=ACCENT).pack(side="left")

        tk.Label(header, text="add account", font=FONT_SM,
                 bg=BG, fg=FG_MUTED).pack(side="right", padx=(0, 4))
        self._btn_add = tk.Button(
            header, text="＋", font=("Consolas", 14, "bold"),
            bg=BG, fg=FG_MUTED, activebackground=BORDER, activeforeground=FG,
            relief="flat", bd=0, cursor="hand2", padx=6,
            command=self._on_add_account)
        self._btn_add.pack(side="right")

        # ── Tab bar ───────────────────────────────────────────────────────────
        self._tab_bar = tk.Frame(self, bg=BG)
        self._tab_bar.pack(fill="x", padx=20, pady=(10, 0))

        # ── Content area ──────────────────────────────────────────────────────
        self._content = tk.Frame(self, bg=BG, bd=0,
                                 highlightthickness=1,
                                 highlightbackground=BORDER)
        self._content.pack(fill="both", expand=True, padx=20, pady=(0, 0))

        self._placeholder = tk.Label(
            self._content,
            text="Click  ＋  to add a YouTube account",
            font=FONT, bg=BG, fg=FG_MUTED)
        self._placeholder.place(relx=0.5, rely=0.4, anchor="center")

        # ── Log box ───────────────────────────────────────────────────────────
        log_frame = tk.LabelFrame(self, text=" Log ", font=FONT_XS,
                                  bg=SURFACE, fg=FG_MUTED, bd=1, relief="flat",
                                  padx=8, pady=6)
        log_frame.pack(fill="x", padx=20, pady=(6, 14))

        log_scroll = tk.Scrollbar(log_frame, bg=BG, troughcolor=BG)
        log_scroll.pack(side="right", fill="y")

        self._log_box = tk.Text(log_frame, height=5, bg=SURFACE2, fg=FG_GREEN,
                                font=FONT_XS, bd=0, highlightthickness=0,
                                state="disabled", yscrollcommand=log_scroll.set)
        self._log_box.pack(fill="x")
        log_scroll.config(command=self._log_box.yview)

    # ── log helper (called by ChannelPanel too) ───────────────────────────────
    def log(self, msg):
        def _write():
            self._log_box.config(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _write)

    # ── account / channel management ─────────────────────────────────────────
    def _load_saved(self):
        channels = load_all_saved_channels()
        self.after(0, lambda: self._add_channels(channels))

    def _on_add_account(self):
        self._btn_add.configure(state="disabled")
        threading.Thread(target=self._add_account_worker, daemon=True).start()

    def _add_account_worker(self):
        try:
            service  = auth_new_account()
            channels = fetch_channels(service)
            self.after(0, lambda: self._add_channels(channels))
        except Exception as e:
            self.after(0, lambda: (
                self._btn_add.configure(state="normal"),
                messagebox.showerror("Auth failed", str(e))
            ))

    def _add_channels(self, new_channels):
        self._btn_add.configure(state="normal")
        existing_ids = {cid for _, cid, _ in self._channels}
        added = [c for c in new_channels if c[1] not in existing_ids]
        self._channels.extend(added)
        for name, cid, svc in added:
            self._create_tab(name, cid, svc)
            self.log(f"Channel loaded: {name}")
        if self._channels and self._active is None:
            self._switch_tab(self._channels[0][0])

    def _create_tab(self, name, channel_id, service):
        btn = tk.Button(
            self._tab_bar, text=name,
            font=FONT_SM,
            bg=BORDER, fg=FG_MUTED,
            activebackground=SURFACE, activeforeground=FG,
            relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
            highlightthickness=0,
            command=lambda n=name: self._switch_tab(n))
        btn.pack(side="left", padx=(0, 2))
        self._tab_btns[name] = btn

        panel = ChannelPanel(self._content, name, channel_id, service, self)
        self._panels[name] = panel
        self._placeholder.place_forget()

    def _switch_tab(self, name):
        if self._active and self._active in self._tab_btns:
            self._tab_btns[self._active].configure(bg=BORDER, fg=FG_MUTED,
                                                    highlightthickness=0)
            self._panels[self._active].place_forget()
        self._active = name
        self._tab_btns[name].configure(bg=SURFACE, fg=FG,
                                        highlightthickness=1,
                                        highlightbackground=ACCENT)
        self._panels[name].place(x=0, y=0, relwidth=1, relheight=1)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()