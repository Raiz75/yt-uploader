import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timedelta

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
FG_WARN  = "#f0a500"
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

def fetch_playlists(service):
    """Fetch all playlists for the authenticated channel."""
    playlists = []
    req = service.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        resp = req.execute()
        for item in resp.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"]
            })
        req = service.playlists().list_next(req, resp)
    return playlists

def create_playlist(service, title, description="", privacy_status="public"):
    """Create a new playlist and return its ID."""
    try:
        body = {
            "snippet": {
                "title": title,
                "description": description
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        response = service.playlists().insert(
            part="snippet,status",
            body=body
        ).execute()
        return response["id"]
    except googleapiclient.errors.HttpError as e:
        raise Exception(f"Failed to create playlist: {str(e)}")

def add_video_to_playlist(service, playlist_id, video_id):
    """Add a video to a playlist."""
    try:
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
        service.playlistItems().insert(
            part="snippet",
            body=body
        ).execute()
        return True
    except googleapiclient.errors.HttpError as e:
        raise Exception(f"Failed to add video to playlist: {str(e)}")


# ── Upload ────────────────────────────────────────────────────────────────────
def upload_video(service, file_path, channel_id, title, description, tags,
                 progress_cb, done_cb, error_cb, thumb_path=None, publish_at=None):
    """
    publish_at: datetime (local time) or None.
      - None      → uploaded as private immediately.
      - datetime  → uploaded as YouTube-scheduled; becomes public at that time.
    """
    status_body = {"privacyStatus": "private"}
    if publish_at is not None:
        # YouTube requires UTC ISO 8601 with Z suffix
        utc_offset  = datetime.now() - datetime.utcnow()
        publish_utc = publish_at - utc_offset
        status_body["publishAt"] = publish_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        status_body["privacyStatus"] = "private"   # must stay "private" for scheduling

    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        tags,
            "categoryId":  "22",
            "channelId":   channel_id,
        },
        "status": status_body,
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

        if thumb_path and os.path.isfile(thumb_path) and video_id != "unknown":
            try:
                service.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumb_path)
                ).execute()
            except googleapiclient.errors.HttpError as te:
                done_cb(video_id, thumb_warning=str(te))
                return

        done_cb(video_id)

    except googleapiclient.errors.HttpError as e:
        error_cb(str(e))
    except Exception as e:
        error_cb(str(e))


# ── Queue Item ────────────────────────────────────────────────────────────────
class QueueItem:
    """Holds state for one file in the upload queue."""
    def __init__(self, file_path, lyrics_path=None, thumb_path=None):
        self.file_path   = file_path
        self.lyrics_path = lyrics_path
        self.thumb_path  = thumb_path
        self.basename    = os.path.basename(file_path)
        # schedule: None = immediate, datetime = scheduled time
        self.scheduled_dt = None
        # playlist: None = no playlist, dict with id/title = add to playlist
        self.playlist    = None
        # status: "pending" | "waiting" | "uploading" | "done" | "error" | "cancelled"
        self.status       = "pending"
        self.progress     = 0
        self.video_id     = None
        self.error_msg    = None
        self._timer       = None   # threading.Timer handle

    def cancel_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


# ── Schedule Picker Dialog ────────────────────────────────────────────────────
class ScheduleDialog(tk.Toplevel):
    """Modal dialog to pick a future datetime for one queue item."""

    def __init__(self, parent, item: QueueItem):
        super().__init__(parent)
        self.title("Schedule Upload")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.result = None  # datetime or None (immediate)

        now = datetime.now() + timedelta(minutes=5)

        tk.Label(self, text=f"Schedule: {item.basename}",
                 font=FONT_SM, bg=BG, fg=FG, wraplength=340).pack(padx=20, pady=(16, 8))

        row = tk.Frame(self, bg=BG)
        row.pack(padx=20, pady=4)

        # Date fields
        tk.Label(row, text="Date (YYYY-MM-DD):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=0, column=0, sticky="w", pady=2)
        self._date_var = tk.StringVar(value=now.strftime("%Y-%m-%d"))
        tk.Entry(row, textvariable=self._date_var, font=FONT_SM,
                 bg=SURFACE2, fg=FG, insertbackground=FG,
                 relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 width=14).grid(row=0, column=1, padx=(8, 0), ipady=5)

        # Hour
        tk.Label(row, text="Hour (0-23):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=1, column=0, sticky="w", pady=2)
        self._hour_var = tk.StringVar(value=str(now.hour))
        ttk.Spinbox(row, from_=0, to=23, textvariable=self._hour_var,
                    width=5, font=FONT_SM).grid(row=1, column=1, padx=(8, 0), sticky="w", ipady=4)

        # Minute
        tk.Label(row, text="Minute (0-59):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=2, column=0, sticky="w", pady=2)
        self._min_var = tk.StringVar(value=str(now.minute))
        ttk.Spinbox(row, from_=0, to=59, textvariable=self._min_var,
                    width=5, font=FONT_SM).grid(row=2, column=1, padx=(8, 0), sticky="w", ipady=4)

        # Buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(12, 16), padx=20, fill="x")
        tk.Button(btn_row, text="Upload Now", font=FONT_SM,
                  bg=BORDER, fg=FG, relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._immediate).pack(side="left")
        tk.Button(btn_row, text="Set Schedule", font=FONT_SM,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._schedule).pack(side="right")

        self.wait_window()

    def _immediate(self):
        self.result = None
        self.destroy()

    def _schedule(self):
        try:
            dt = datetime.strptime(
                f"{self._date_var.get()} {int(self._hour_var.get()):02d}:{int(self._min_var.get()):02d}",
                "%Y-%m-%d %H:%M"
            )
        except ValueError:
            messagebox.showerror("Invalid date", "Check date format: YYYY-MM-DD", parent=self)
            return
        if dt <= datetime.now():
            messagebox.showerror("Invalid time", "Scheduled time must be in the future.", parent=self)
            return
        self.result = dt
        self.destroy()


# ── Bulk Schedule Dialog ──────────────────────────────────────────────────────
class BulkScheduleDialog(tk.Toplevel):
    """Modal dialog to schedule multiple files across a date range."""

    def __init__(self, parent, item_count):
        super().__init__(parent)
        self.title("Bulk Schedule")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.result = None  # dict with start_date, end_date, upload_time or None

        now = datetime.now() + timedelta(minutes=5)
        tomorrow = now + timedelta(days=1)

        tk.Label(self, text=f"Bulk Schedule {item_count} Files",
                 font=FONT_LG, bg=BG, fg=FG).pack(padx=20, pady=(16, 8))

        tk.Label(self, text="Files will be distributed equally across the date range.\nEarlier days get extra files if uneven.",
                 font=FONT_XS, bg=BG, fg=FG_MUTED, justify="center").pack(padx=20, pady=(0, 12))

        row = tk.Frame(self, bg=BG)
        row.pack(padx=20, pady=4)

        # Start Date
        tk.Label(row, text="Start Date (YYYY-MM-DD):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=0, column=0, sticky="w", pady=4)
        self._start_var = tk.StringVar(value=now.strftime("%Y-%m-%d"))
        tk.Entry(row, textvariable=self._start_var, font=FONT_SM,
                 bg=SURFACE2, fg=FG, insertbackground=FG,
                 relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 width=14).grid(row=0, column=1, padx=(8, 0), ipady=5)

        # End Date
        tk.Label(row, text="End Date (YYYY-MM-DD):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=1, column=0, sticky="w", pady=4)
        self._end_var = tk.StringVar(value=tomorrow.strftime("%Y-%m-%d"))
        tk.Entry(row, textvariable=self._end_var, font=FONT_SM,
                 bg=SURFACE2, fg=FG, insertbackground=FG,
                 relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 width=14).grid(row=1, column=1, padx=(8, 0), ipady=5)

        # Upload Time (same for all files each day)
        tk.Label(row, text="Upload Time (HH:MM):", font=FONT_XS, bg=BG, fg=FG_MUTED).grid(
            row=2, column=0, sticky="w", pady=4)
        time_frame = tk.Frame(row, bg=BG)
        time_frame.grid(row=2, column=1, padx=(8, 0), sticky="w")
        
        self._hour_var = tk.StringVar(value=str(now.hour))
        ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self._hour_var,
                    width=3, font=FONT_SM).pack(side="left", ipady=4)
        tk.Label(time_frame, text=":", font=FONT_SM, bg=BG, fg=FG).pack(side="left", padx=2)
        self._min_var = tk.StringVar(value=str(now.minute))
        ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self._min_var,
                    width=3, font=FONT_SM).pack(side="left", ipady=4)

        # Preview
        self._preview_lbl = tk.Label(self, text="", font=FONT_XS,
                                     bg=SURFACE, fg=FG_MUTED, justify="left",
                                     relief="flat", bd=1, padx=10, pady=8)
        self._preview_lbl.pack(padx=20, pady=12, fill="x")

        # Update preview on field changes
        self._start_var.trace_add("write", self._update_preview)
        self._end_var.trace_add("write", self._update_preview)
        self._update_preview()

        # Buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(0, 16), padx=20, fill="x")
        tk.Button(btn_row, text="Cancel", font=FONT_SM,
                  bg=BORDER, fg=FG, relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._cancel).pack(side="left")
        tk.Button(btn_row, text="Apply Schedule", font=FONT_SM,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=self._apply).pack(side="right")

        self.wait_window()

    def _update_preview(self, *args):
        try:
            start = datetime.strptime(self._start_var.get(), "%Y-%m-%d")
            end = datetime.strptime(self._end_var.get(), "%Y-%m-%d")
            if end < start:
                self._preview_lbl.config(text="⚠ End date must be after start date", fg=ACCENT)
                return
            days = (end - start).days + 1
            self._preview_lbl.config(
                text=f"Date range: {days} day(s)\n{start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}",
                fg=FG_MUTED)
        except ValueError:
            self._preview_lbl.config(text="Invalid date format", fg=ACCENT)

    def _cancel(self):
        self.result = None
        self.destroy()

    def _apply(self):
        try:
            start_date = datetime.strptime(self._start_var.get(), "%Y-%m-%d")
            end_date = datetime.strptime(self._end_var.get(), "%Y-%m-%d")
            hour = int(self._hour_var.get())
            minute = int(self._min_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Check date format: YYYY-MM-DD and time values", parent=self)
            return

        if end_date < start_date:
            messagebox.showerror("Invalid range", "End date must be on or after start date.", parent=self)
            return

        # Combine date with time
        upload_time = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if upload_time <= datetime.now():
            messagebox.showerror("Invalid time", "First scheduled time must be in the future.", parent=self)
            return

        self.result = {
            "start_date": start_date,
            "end_date": end_date,
            "hour": hour,
            "minute": minute
        }
        self.destroy()


# ── Queue Row Widget ──────────────────────────────────────────────────────────
class QueueRow(tk.Frame):
    """One row in the queue list representing a QueueItem."""

    def __init__(self, parent, item: QueueItem, on_remove, on_schedule, **kw):
        super().__init__(parent, bg=SURFACE, **kw)
        self._item        = item
        self._on_remove   = on_remove
        self._on_schedule = on_schedule
        self._build()

    def _build(self):
        # File name label
        self._name_lbl = tk.Label(
            self, text=self._item.basename, font=FONT_XS,
            bg=SURFACE, fg=FG, anchor="w", width=20)
        self._name_lbl.pack(side="left", padx=(8, 4), pady=4)

        # Schedule label
        self._sched_lbl = tk.Label(
            self, text="now", font=FONT_XS,
            bg=SURFACE, fg=FG_MUTED, anchor="w", width=12)
        self._sched_lbl.pack(side="left", padx=4)

        # Playlist label
        playlist_title = self._item.playlist["title"] if self._item.playlist else ""
        self._playlist_lbl = tk.Label(
            self, text=playlist_title, font=FONT_XS,
            bg=SURFACE, fg=FG_MUTED, anchor="w", width=10)
        self._playlist_lbl.pack(side="left", padx=4)

        # Progress / status label
        self._status_lbl = tk.Label(
            self, text="pending", font=FONT_XS,
            bg=SURFACE, fg=FG_MUTED, anchor="w", width=10)
        self._status_lbl.pack(side="left", padx=4)

        # Progress bar (compact)
        self._pbar = ttk.Progressbar(
            self, maximum=100, length=80,
            style="red.Horizontal.TProgressbar")
        self._pbar.pack(side="left", padx=4)

        # Schedule button
        tk.Button(self, text="🕐", font=FONT_XS,
                  bg=SURFACE, fg=FG_MUTED, relief="flat", bd=0,
                  cursor="hand2", padx=4,
                  command=lambda: self._on_schedule(self._item, self)
                  ).pack(side="left", padx=2)

        # Remove button
        tk.Button(self, text="✕", font=FONT_XS,
                  bg=SURFACE, fg=FG_MUTED, relief="flat", bd=0,
                  cursor="hand2", padx=4,
                  command=lambda: self._on_remove(self._item, self)
                  ).pack(side="left", padx=(2, 8))

    def update_schedule_label(self):
        if self._item.scheduled_dt:
            self._sched_lbl.configure(
                text=self._item.scheduled_dt.strftime("%m/%d %H:%M"),
                fg=FG_WARN)
        else:
            self._sched_lbl.configure(text="now", fg=FG_MUTED)

    def update_playlist_label(self):
        title = self._item.playlist["title"] if self._item.playlist else ""
        self._playlist_lbl.configure(text=title, fg=FG_WARN if title else FG_MUTED)

    def update_status(self):
        s = self._item.status
        p = self._item.progress
        color_map = {
            "pending":   FG_MUTED,
            "waiting":   FG_WARN,
            "uploading": FG,
            "done":      FG_GREEN,
            "error":     ACCENT,
            "cancelled": FG_MUTED,
        }
        self._status_lbl.configure(text=s, fg=color_map.get(s, FG_MUTED))
        self._pbar["value"] = p if s == "uploading" else (100 if s == "done" else 0)


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

        self._queue       = []    # list[QueueItem]
        self._queue_rows  = {}    # QueueItem -> QueueRow
        self._uploading   = False
        self._playlists   = []    # list of {"id": ..., "title": ...}
        self._selected_playlist = None  # Currently selected playlist dict or None

        self._build()
        # Load playlists in background
        threading.Thread(target=self._load_playlists, daemon=True).start()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lf(self, label):
        return tk.LabelFrame(self, text=f" {label} ", font=FONT_XS,
                             bg=SURFACE, fg=FG_MUTED, bd=1, relief="flat",
                             padx=10, pady=8)

    # ── build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        # ── Add files section ─────────────────────────────────────────────────
        af = self._lf("Add Files to Queue")
        af.pack(fill="x", padx=16, pady=(14, 6))

        add_row = tk.Frame(af, bg=SURFACE)
        add_row.pack(fill="x")
        tk.Button(add_row, text="＋ Add Video(s)", font=FONT_SM,
                  bg=BORDER, fg=FG, activebackground="#1a3a6e",
                  relief="flat", bd=0, padx=12, cursor="hand2",
                  command=self._browse_videos, pady=6
                  ).pack(side="left")
        if self.is_restore:
            tk.Label(add_row,
                     text="  Lyrics/thumb auto-matched by filename (same basename)",
                     font=FONT_XS, bg=SURFACE, fg=FG_MUTED
                     ).pack(side="left", padx=8)

        # ── Playlist section ──────────────────────────────────────────────────
        pf = self._lf("Playlist (optional)")
        pf.pack(fill="x", padx=16, pady=(0, 6))

        playlist_row = tk.Frame(pf, bg=SURFACE)
        playlist_row.pack(fill="x")

        tk.Label(playlist_row, text="Add to:", font=FONT_XS,
                 bg=SURFACE, fg=FG_MUTED).pack(side="left", padx=(0, 8))

        self._playlist_var = tk.StringVar(value="None")
        self._playlist_dropdown = ttk.Combobox(
            playlist_row, textvariable=self._playlist_var,
            font=FONT_SM, width=25, state="readonly")
        self._playlist_dropdown["values"] = ["None", "Loading..."]
        self._playlist_dropdown.pack(side="left", padx=4)
        self._playlist_dropdown.bind("<<ComboboxSelected>>", self._on_playlist_selected)

        tk.Button(playlist_row, text="🔄", font=FONT_SM,
                  bg=SURFACE, fg=FG_MUTED, relief="flat", bd=0,
                  cursor="hand2", padx=6,
                  command=self._refresh_playlists
                  ).pack(side="left", padx=2)

        tk.Button(playlist_row, text="➕ New", font=FONT_SM,
                  bg=BORDER, fg=FG, activebackground="#1a3a6e",
                  relief="flat", bd=0, padx=8, pady=4,
                  cursor="hand2", command=self._create_new_playlist
                  ).pack(side="left", padx=4)

        tk.Button(playlist_row, text="Apply to All", font=FONT_SM,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", bd=0, padx=8, pady=4,
                  cursor="hand2", command=self._apply_playlist_to_all
                  ).pack(side="right")

        # ── Queue list ────────────────────────────────────────────────────────
        qf = self._lf("Upload Queue")
        qf.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        canvas_frame = tk.Frame(qf, bg=SURFACE)
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(canvas_frame, bg=SURFACE2, bd=0,
                                 highlightthickness=0, height=140)
        scroll = tk.Scrollbar(canvas_frame, orient="vertical",
                              command=self._canvas.yview, bg=BG)
        self._canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._queue_frame = tk.Frame(self._canvas, bg=SURFACE2)
        self._canvas_win  = self._canvas.create_window(
            (0, 0), window=self._queue_frame, anchor="nw")
        self._queue_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._empty_lbl = tk.Label(self._queue_frame,
                                   text="No files in queue. Click  ＋ Add Video(s)  above.",
                                   font=FONT_XS, bg=SURFACE2, fg=FG_MUTED)
        self._empty_lbl.pack(pady=20)

        # ── Upload button ─────────────────────────────────────────────────────
        self._btn_upload = tk.Button(
            self, text="⬆  Upload Queue",
            font=FONT_LG,
            bg=ACCENT, fg="white", activebackground=ACCENT2,
            relief="flat", bd=0, cursor="hand2", padx=10, pady=10,
            command=self._on_start_queue)
        self._btn_upload.pack(fill="x", padx=16, pady=(0, 6))

        # ── Bulk schedule and clear buttons ───────────────────────────────────
        bottom_row = tk.Frame(self, bg=BG)
        bottom_row.pack(fill="x", padx=16, pady=(0, 10))
        
        tk.Button(bottom_row, text="📅 Bulk Schedule", font=FONT_SM,
                  bg=BORDER, fg=FG, activebackground="#1a3a6e",
                  relief="flat", bd=0, padx=10, pady=5,
                  cursor="hand2", command=self._open_bulk_schedule
                  ).pack(side="left")
        
        tk.Button(bottom_row, text="Clear Done / Error", font=FONT_XS,
                  bg=SURFACE, fg=FG_MUTED, relief="flat", bd=0, padx=8, pady=4,
                  cursor="hand2", command=self._clear_done
                  ).pack(side="right")

    def _on_frame_configure(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._canvas_win, width=e.width)

    # ── playlist management ───────────────────────────────────────────────────
    def _load_playlists(self):
        """Load playlists from YouTube in background thread."""
        try:
            self._playlists = fetch_playlists(self.service)
            playlist_titles = ["None"] + [p["title"] for p in self._playlists]
            self.after(0, lambda: self._playlist_dropdown.configure(values=playlist_titles))
            self.after(0, lambda: self._playlist_var.set("None"))
            self.app.log(f"Loaded {len(self._playlists)} playlists for {self.channel_name}")
        except Exception as e:
            self.app.log(f"Failed to load playlists: {str(e)}")
            self.after(0, lambda: self._playlist_dropdown.configure(values=["None", "Error loading"]))

    def _refresh_playlists(self):
        """Refresh playlist list."""
        self._playlist_dropdown.configure(values=["None", "Loading..."])
        self._playlist_var.set("Loading...")
        threading.Thread(target=self._load_playlists, daemon=True).start()

    def _on_playlist_selected(self, event=None):
        """Handle playlist selection from dropdown."""
        selected_title = self._playlist_var.get()
        if selected_title == "None":
            self._selected_playlist = None
        else:
            # Find the playlist dict by title
            self._selected_playlist = next(
                (p for p in self._playlists if p["title"] == selected_title),
                None
            )

    def _create_new_playlist(self):
        """Open dialog to create a new playlist."""
        dialog = tk.Toplevel(self)
        dialog.title("Create New Playlist")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        tk.Label(dialog, text="New Playlist", font=FONT_LG,
                 bg=BG, fg=FG).pack(padx=20, pady=(16, 8))

        # Title input
        tk.Label(dialog, text="Playlist Title:", font=FONT_XS,
                 bg=BG, fg=FG_MUTED).pack(padx=20, anchor="w")
        title_var = tk.StringVar()
        tk.Entry(dialog, textvariable=title_var, font=FONT_SM,
                 bg=SURFACE2, fg=FG, insertbackground=FG,
                 relief="flat", bd=0, width=30,
                 highlightthickness=1, highlightbackground=BORDER
                 ).pack(padx=20, pady=(4, 12), ipady=5)

        # Privacy selection
        tk.Label(dialog, text="Privacy:", font=FONT_XS,
                 bg=BG, fg=FG_MUTED).pack(padx=20, anchor="w")
        privacy_var = tk.StringVar(value="public")
        privacy_frame = tk.Frame(dialog, bg=BG)
        privacy_frame.pack(padx=20, pady=(4, 16))
        for val in ["public", "unlisted", "private"]:
            tk.Radiobutton(privacy_frame, text=val.capitalize(),
                          variable=privacy_var, value=val,
                          font=FONT_SM, bg=BG, fg=FG,
                          selectcolor=SURFACE, activebackground=BG,
                          activeforeground=FG).pack(side="left", padx=8)

        # Buttons
        btn_row = tk.Frame(dialog, bg=BG)
        btn_row.pack(pady=(0, 16), padx=20, fill="x")
        
        def on_create():
            title = title_var.get().strip()
            if not title:
                messagebox.showerror("Invalid input", "Playlist title cannot be empty.", parent=dialog)
                return
            dialog.destroy()
            threading.Thread(target=self._create_playlist_worker,
                           args=(title, privacy_var.get()), daemon=True).start()

        tk.Button(btn_row, text="Cancel", font=FONT_SM,
                  bg=BORDER, fg=FG, relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=dialog.destroy).pack(side="left")
        tk.Button(btn_row, text="Create", font=FONT_SM,
                  bg=ACCENT, fg="white", activebackground=ACCENT2,
                  relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2", command=on_create).pack(side="right")

    def _create_playlist_worker(self, title, privacy):
        """Create playlist in background thread."""
        try:
            playlist_id = create_playlist(self.service, title, privacy_status=privacy)
            new_playlist = {"id": playlist_id, "title": title}
            self._playlists.append(new_playlist)
            playlist_titles = ["None"] + [p["title"] for p in self._playlists]
            self.after(0, lambda: self._playlist_dropdown.configure(values=playlist_titles))
            self.after(0, lambda: self._playlist_var.set(title))
            self._selected_playlist = new_playlist
            self.app.log(f"✓ Created playlist: {title} ({privacy})")
        except Exception as e:
            self.app.log(f"✖ Failed to create playlist: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Playlist Error", str(e)))

    def _apply_playlist_to_all(self):
        """Apply selected playlist to all pending items."""
        if not self._selected_playlist:
            messagebox.showinfo("No playlist selected", "Please select a playlist first.")
            return
        
        pending = [i for i in self._queue if i.status in ("pending", "waiting")]
        if not pending:
            messagebox.showinfo("No items", "No pending items in queue.")
            return

        for item in pending:
            item.playlist = self._selected_playlist
            row = self._queue_rows.get(id(item))
            if row:
                row.update_playlist_label()

        self.app.log(f"Applied playlist '{self._selected_playlist['title']}' to {len(pending)} items")
        messagebox.showinfo("Playlist Applied",
                          f"All {len(pending)} pending items will be added to:\n{self._selected_playlist['title']}")

    # ── browse / queue management ─────────────────────────────────────────────
    def _browse_videos(self):
        paths = filedialog.askopenfilenames(
            title="Select video file(s)",
            filetypes=[("MP4 files", "*.mp4"),
                       ("All video files", "*.mp4 *.mov *.avi *.mkv")])
        for path in paths:
            self._add_to_queue(path)

    def _add_to_queue(self, file_path):
        # Deduplicate
        if any(i.file_path == file_path for i in self._queue):
            self.app.log(f"Already queued: {os.path.basename(file_path)}")
            return

        if self.is_restore:
            base      = os.path.splitext(file_path)[0]
            lpath     = base + ".txt"  if os.path.isfile(base + ".txt")  else None
            tpath     = base + ".png"  if os.path.isfile(base + ".png")  else None
            item      = QueueItem(file_path, lyrics_path=lpath, thumb_path=tpath)
            missing   = []
            if not lpath: missing.append("lyrics (.txt)")
            if not tpath: missing.append("thumbnail (.png)")
            if missing:
                self.app.log(f"⚠ {os.path.basename(file_path)}: missing {', '.join(missing)} (auto-match by filename)")
        else:
            item = QueueItem(file_path)

        # Inherit the currently selected playlist
        if self._selected_playlist:
            item.playlist = self._selected_playlist

        self._queue.append(item)
        self._render_queue_row(item)
        playlist_note = f" → playlist: {item.playlist['title']}" if item.playlist else ""
        self.app.log(f"Queued: {item.basename}{playlist_note}")

    def _render_queue_row(self, item: QueueItem):
        if self._empty_lbl.winfo_ismapped():
            self._empty_lbl.pack_forget()

        row = QueueRow(self._queue_frame, item,
                       on_remove=self._remove_item,
                       on_schedule=self._open_schedule_dialog)
        row.pack(fill="x", pady=1)
        self._queue_rows[id(item)] = row

    def _remove_item(self, item: QueueItem, row: QueueRow):
        if item.status in ("uploading", "waiting"):
            item.cancel_timer()
            item.status = "cancelled"
        self._queue.remove(item)
        del self._queue_rows[id(item)]
        row.destroy()
        if not self._queue:
            self._empty_lbl.pack(pady=20)
        self.app.log(f"Removed: {item.basename}")

    def _open_schedule_dialog(self, item: QueueItem, row: QueueRow):
        if item.status not in ("pending", "waiting"):
            return
        dlg = ScheduleDialog(self, item)
        item.scheduled_dt = dlg.result
        item.status = "waiting" if dlg.result else "pending"
        row.update_schedule_label()
        row.update_status()
        if dlg.result:
            self.app.log(f"Scheduled: {item.basename} → {dlg.result.strftime('%Y-%m-%d %H:%M')}")

    def _open_bulk_schedule(self):
        # Only schedule pending/waiting items
        schedulable = [i for i in self._queue if i.status in ("pending", "waiting")]
        if not schedulable:
            messagebox.showinfo("No items", "No pending items to schedule.")
            return

        dlg = BulkScheduleDialog(self, len(schedulable))
        if not dlg.result:
            return  # User cancelled

        # Extract schedule parameters
        start_date = dlg.result["start_date"]
        end_date = dlg.result["end_date"]
        hour = dlg.result["hour"]
        minute = dlg.result["minute"]

        # Calculate distribution
        total_days = (end_date - start_date).days + 1
        total_files = len(schedulable)
        files_per_day = total_files // total_days
        extra_files = total_files % total_days

        # Distribute files across dates (earlier days get extras)
        schedule_map = []
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            files_today = files_per_day + (1 if day_offset < extra_files else 0)
            for _ in range(files_today):
                schedule_dt = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                schedule_map.append(schedule_dt)

        # Apply schedules to items
        for item, sched_dt in zip(schedulable, schedule_map):
            item.scheduled_dt = sched_dt
            item.status = "waiting"
            row = self._queue_rows.get(id(item))
            if row:
                row.update_schedule_label()
                row.update_status()

        self.app.log(f"Bulk scheduled {total_files} files from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} at {hour:02d}:{minute:02d}")
        messagebox.showinfo("Bulk Schedule Applied", 
                          f"Scheduled {total_files} files across {total_days} day(s).\n"
                          f"{files_per_day} files per day" + 
                          (f" (+{extra_files} extra on earlier days)" if extra_files > 0 else ""))

    def _clear_done(self):
        to_remove = [i for i in self._queue if i.status in ("done", "error", "cancelled")]
        for item in to_remove:
            row = self._queue_rows.pop(id(item), None)
            if row:
                row.destroy()
            self._queue.remove(item)
        if not self._queue:
            self._empty_lbl.pack(pady=20)

    # ── queue execution ───────────────────────────────────────────────────────
    def _on_start_queue(self):
        pending = [i for i in self._queue if i.status in ("pending", "waiting")]
        if not pending:
            messagebox.showinfo("Queue empty", "No pending items in the queue.")
            return
        if self._uploading:
            messagebox.showinfo("Busy", "An upload is already running.")
            return
        # Validate Restore items have lyrics
        for item in pending:
            if self.is_restore and not item.lyrics_path:
                messagebox.showwarning(
                    "Missing lyrics",
                    f"No lyrics file for:\n{item.basename}\n\nPlace a .txt with the same name next to the video.")
                return
        self._btn_upload.configure(state="disabled", text="Running queue…")
        threading.Thread(target=self._run_queue, args=(pending,), daemon=True).start()

    def _run_queue(self, items):
        self._uploading = True
        for item in items:
            item.status   = "uploading"
            item.progress = 0
            self._refresh_row(item)
            sched_info = (f" [scheduled {item.scheduled_dt.strftime('%m/%d %H:%M')}]"
                          if item.scheduled_dt else "")
            self.app.log(f"\nUploading → {item.basename}{sched_info}")

            # Build metadata
            if self.is_restore:
                title = os.path.splitext(item.basename)[0]
                with open(item.lyrics_path, "r", encoding="utf-8") as fh:
                    lyrics = fh.read().strip()
                description = f"{CH2_DESC_PREFIX}\n\n{title}\n\n{lyrics}"
                tags        = CH2_TAGS
                tpath       = item.thumb_path
            else:
                title       = CH1_TITLE
                description = CH1_DESCRIPTION
                tags        = CH1_TAGS
                tpath       = None

            # Blocking upload (runs in this thread)
            _done   = threading.Event()
            _result = {}

            def _progress(pct, _item=item):
                _item.progress = pct
                self._refresh_row(_item)
                if pct % 25 == 0:
                    self.app.log(f"  {pct}%")

            def _done_cb(video_id, thumb_warning=None, _item=item, _ev=_done, _r=_result):
                _item.status    = "done"
                _item.progress  = 100
                _item.video_id  = video_id
                _r["thumb_warning"] = thumb_warning
                _ev.set()

            def _error_cb(msg, _item=item, _ev=_done, _r=_result):
                _item.status    = "error"
                _item.error_msg = msg
                _r["error"]     = msg
                _ev.set()

            publish_at = item.scheduled_dt  # datetime or None
            if publish_at:
                self.app.log(f"  Scheduling for: {publish_at.strftime('%Y-%m-%d %H:%M')} (local)")
            upload_video(self.service, item.file_path, self.channel_id,
                         title, description, tags,
                         _progress, _done_cb, _error_cb,
                         thumb_path=tpath, publish_at=publish_at)
            _done.wait()
            self._refresh_row(item)

            if "error" in _result:
                self.app.log(f"  ✖ Error: {_result['error']}")
                self.after(0, lambda m=_result["error"]: messagebox.showerror("Upload failed", m))
            else:
                tw = _result.get("thumb_warning")
                sched_str = (f"  Scheduled: {item.scheduled_dt.strftime('%Y-%m-%d %H:%M')}"
                             if item.scheduled_dt else "  Status: Private")
                if tw:
                    self.app.log(f"  ✔ Done — ID: {item.video_id}  ⚠ Thumbnail: {tw}\n{sched_str}")
                else:
                    self.app.log(f"  ✔ Done — ID: {item.video_id}\n{sched_str}")

                # Add to playlist if one is assigned to this item
                if item.playlist and item.video_id and item.video_id != "unknown":
                    try:
                        add_video_to_playlist(self.service, item.playlist["id"], item.video_id)
                        self.app.log(f"  ✔ Added to playlist: {item.playlist['title']}")
                    except Exception as pe:
                        self.app.log(f"  ⚠ Playlist add failed: {pe}")

        self._uploading = False
        self.after(0, lambda: self._btn_upload.configure(
            state="normal", text="⬆  Upload Queue"))
        self.after(0, lambda: messagebox.showinfo(
            "Queue complete", "All queued uploads finished."))

    def _refresh_row(self, item: QueueItem):
        row = self._queue_rows.get(id(item))
        if row:
            self.after(0, row.update_status)


# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YT Uploader")
        self.geometry("680x680")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._channels = []
        self._panels   = {}
        self._tab_btns = {}
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
                        thickness=6)

    def _build_ui(self):
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

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

        self._tab_bar = tk.Frame(self, bg=BG)
        self._tab_bar.pack(fill="x", padx=20, pady=(10, 0))

        self._content = tk.Frame(self, bg=BG, bd=0,
                                 highlightthickness=1,
                                 highlightbackground=BORDER)
        self._content.pack(fill="both", expand=True, padx=20, pady=(0, 0))

        self._placeholder = tk.Label(
            self._content,
            text="Click  ＋  to add a YouTube account",
            font=FONT, bg=BG, fg=FG_MUTED)
        self._placeholder.place(relx=0.5, rely=0.4, anchor="center")

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

    def log(self, msg):
        def _write():
            self._log_box.config(state="normal")
            self._log_box.insert("end", msg + "\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _write)

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
            self._tab_bar, text=name, font=FONT_SM,
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
