# YT Uploader — Setup Guide

A desktop GUI tool for uploading videos to YouTube with support for scheduling, playlists, and multi-account management.

---

## Requirements

- **Python 3.x** (tested on 3.14 based on compiled cache)
- **Windows** (launcher is a `.vbs` script; the Python script itself is cross-platform)
- A Google account with a YouTube channel
- A Google Cloud project with the YouTube Data API v3 enabled

---

## 1. Google Cloud Setup

### 1.1 Create a Project & Enable the API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **YouTube Data API v3** and click **Enable**

### 1.2 Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Set application type to **Desktop app**
4. Name it anything (e.g. `yt-uploader`)
5. Click **Create**
6. Download the JSON file → rename it to `client_secrets.json`
7. Place `client_secrets.json` in the project root:

```
yt-uploader/
├── client_secrets.json   ← here
├── video-uploader.py
├── requirements.txt
└── ...
```

> ⚠️ `client_secrets.json` is git-ignored. Never commit it.

### 1.3 Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Set user type to **External**
3. Fill in the required app info (name, support email)
4. Under **Scopes**, add: `https://www.googleapis.com/auth/youtube`
5. Under **Test users**, add the Google accounts you'll be uploading from
6. Save

---

## 2. Python Environment Setup

### 2.1 Install Dependencies

```bash
cd path/to/yt-uploader
pip install -r requirements.txt
```

Packages installed:

| Package | Version |
|---|---|
| google-api-python-client | 2.126.0 |
| google-auth-httplib2 | 0.2.0 |
| google-auth-oauthlib | 1.2.0 |

> `tkinter` is included with standard Python on Windows. No separate install needed.

---

## 3. Running the App

### Option A — VBS Launcher (no console window)

Double-click `run_video-uploader.vbs`

This runs the script silently (no terminal window) with the working directory set to the project folder.

### Option B — Terminal

```bash
cd path/to/yt-uploader
python video-uploader.py
```

---

## 4. First Launch — Account Authentication

1. Click the **＋** button in the top-right of the app
2. A browser window will open → sign in with your Google account
3. Grant the requested YouTube permissions
4. The app saves credentials as `tokens/token_N.pickle`
5. Your channel tab will appear in the UI

> Tokens are git-ignored. Subsequent launches load saved tokens automatically — no re-auth needed unless tokens expire.

### Multi-Account Support

Repeat the **＋** flow for each additional account. Each account gets its own tab per channel.

---

## 5. File Structure Reference

```
yt-uploader/
├── video-uploader.py         # Main application
├── run_video-uploader.vbs    # Silent Windows launcher
├── requirements.txt          # Python dependencies
├── client_secrets.json       # OAuth credentials (git-ignored, you provide this)
├── tokens/
│   ├── .gitkeep
│   └── token_N.pickle        # Saved auth tokens (git-ignored, auto-generated)
└── .gitignore
```

---

## 6. Channel Modes

The app detects channel type by name (case-insensitive):

### Standard Channel (default)
- Fixed title, description, and tags defined in `CH1_TITLE`, `CH1_DESCRIPTION`, `CH1_TAGS` at the top of `video-uploader.py`
- No thumbnail or lyrics required

### Restore Channel
- Detected when channel name matches `"restore"` (configurable via `RESTORE_CHANNEL_NAME`)
- Expects companion files with the **same basename** as the video:
  - `.txt` → lyrics (appended to description)
  - `.png` → thumbnail (uploaded via thumbnails API)
- Title is derived from the video filename (without extension)

Example for Restore channel:
```
my_song.mp4
my_song.txt    ← lyrics
my_song.png    ← thumbnail
```

---

## 7. Usage

### Uploading Videos

1. Select a channel tab
2. Click **＋ Add Video(s)** → select one or more `.mp4` files
3. Optionally set a playlist and/or schedule (see below)
4. Click **⬆ Upload Queue**

### Scheduling

- **Per-file**: Click the 🕐 icon on any queue row → set date/time
- **Bulk**: Click **📅 Bulk Schedule** → set a date range and upload time; files are distributed evenly across days

Scheduled videos are uploaded as **private** with YouTube's `publishAt` field set, making them go public automatically at the scheduled UTC time.

### Playlists

- Select an existing playlist from the dropdown, or click **➕ New** to create one
- Click **Apply to All** to assign the selected playlist to all pending queue items
- Per-item playlist assignment inherits from the dropdown at time of file add

---

## 8. Customizing Defaults

Edit the config block at the top of `video-uploader.py`:

```python
# ── Channel 1 defaults ──
CH1_TITLE       = "quote of the day"
CH1_DESCRIPTION = "..."
CH1_TAGS        = [...]

# ── Channel 2 (Restore) defaults ──
CH2_DESC_PREFIX = "..."
CH2_TAGS        = [...]

RESTORE_CHANNEL_NAME = "restore"   # channel name to trigger Restore mode
```

---

## 9. Troubleshooting

| Issue | Fix |
|---|---|
| `client_secrets.json not found` | Place the file in the project root (same folder as `video-uploader.py`) |
| Auth browser doesn't open | Run from terminal to see the error; check firewall/proxy |
| `400: redirect_uri_mismatch` | Ensure OAuth client type is set to **Desktop app** |
| Channel not appearing | Verify the Google account has an active YouTube channel |
| Thumbnail upload fails | Must be PNG/JPG under 2MB; channel must be verified for custom thumbnails |
| Token expired | Delete `tokens/token_N.pickle` and re-authenticate via **＋** |
| `quota exceeded` | YouTube Data API v3 has a 10,000 unit/day quota by default; each upload costs ~1,600 units |
