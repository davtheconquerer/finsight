<div align="center">
  <h1>FinSight</h1>
  <p><strong>Open-source monitoring and statistics dashboard for Jellyfin</strong></p>
  <p>Inspired by Tautulli &middot; Built with FastAPI + Chart.js + SQLite</p>
</div>

---

FinSight is a lightweight sidecar application that connects to your Jellyfin server via its API to provide real-time monitoring, historical playback analytics, transcode visibility, library management tools, and weekly email digests &mdash; all in a single Docker container.

## Features

- **Live Dashboard** &mdash; Active streams, plays-over-time chart, top media, recent activity
- **Transcode Shaming** &mdash; See who is transcoding, why, and from which device
- **Playback History** &mdash; Filterable, paginated log with user/media search
- **Media Detail** &mdash; Per-item play count, transcode ratio, and full play history
- **Library Janitor** &mdash; Identify cold media not played in N months, with CSV export
- **User Stats** &mdash; Per-user play counts, transcode ratio, device breakdown
- **Weekly Digest** &mdash; Auto-generated email-ready HTML with top media, users, genre breakdown
- **Prometheus Metrics** &mdash; `/api/metrics` endpoint for Grafana integration
- **Polling-first** &mdash; Works out of the box without Jellyfin Webhook plugin

## Quick Start

### Docker (recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/finsight.git
cd finsight

# Create .env with your Jellyfin credentials
echo JELLYFIN_API_KEY=your-api-key-here > .env

# Start
docker compose up -d
```

Open `http://localhost:8500`.

### Manual

```bash
cd backend
pip install -r requirements.txt

$env:JELLYFIN_URL="http://localhost:8096"
$env:JELLYFIN_API_KEY="your-api-key-here"
uvicorn app.main:app --host 0.0.0.0 --port 8500 --reload
```

## Configuration

All settings are passed via environment variables or a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `JELLYFIN_URL` | `http://localhost:8096` | Jellyfin server address |
| `JELLYFIN_API_KEY` | — | API key from Jellyfin Dashboard &rarr; API Keys |
| `POLL_INTERVAL` | `30` | Seconds between session polls (user/library poll less frequently) |
| `COLD_MEDIA_MONTHS` | `6` | Months of inactivity to flag media as cold |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Pages

| Route | Description |
|---|---|
| `/` | Dashboard &mdash; stats, charts, active streams, recent history |
| `/transcodes` | Transcode shaming &mdash; live active transcodes, reason breakdown, leaderboard |
| `/history` | Playback history &mdash; filterable and paginated |
| `/media/{id}` | Media detail &mdash; stats and full play history |
| `/newsletter` | Weekly digest &mdash; preview and manual generation |
| `/library` | Library janitor &mdash; cold media scanner with CSV export |
| `/users` | User statistics &mdash; plays, transcodes, devices |

## API Endpoints

```
GET  /api/health
GET  /api/metrics                     # Prometheus format
GET  /api/sessions/active             # Live streams
GET  /api/sessions/history            # Paginated playback log
GET  /api/stats/overview              # Total counts
GET  /api/stats/plays-over-time       # 30-day timeline
GET  /api/stats/top-media             # Most played
GET  /api/stats/transcode-breakdown   # Transcode analysis
GET  /api/media/{id}                  # Media detail + history
GET  /api/library/cold-media          # Cold media list
GET  /api/library/cold-media/export   # CSV download
GET  /api/users/stats                 # Per-user breakdown
POST /newsletter/generate             # Trigger digest
GET  /newsletter/preview              # Latest digest HTML
```

## How It Works

```
Jellyfin API  ──>  Watchdog (polling loop)
                       │
                       ├──> Users table
                       ├──> MediaMetadata table
                       └──> PlaybackSession table
                                │
                    FastAPI ────┤
                       │        │
                  Jinja2 + Chart.js  ──>  Browser
                       │
              Newsletter Scheduler
              Library Janitor (on-demand)
```

The watchdog polls Jellyfin's `/Sessions` every N seconds, `/Users` every 10N seconds, and `/Items` (library) every 60N seconds. Data is upserted into SQLite. The web frontend queries the same database via FastAPI endpoints with Chart.js for visualizations.

## Roadmap

- **Webhook Consumer** &mdash; Process Jellyfin webhook events for real-time updates
- **File Size Tracking** &mdash; Poll `MediaSources` for per-item disk usage
- **Authentication** &mdash; Simple login for multi-user access
- **Notifications** &mdash; Email/Slack/Discord alerts for transcode events
- **Test Suite** &mdash; pytest coverage for services and endpoints
- **i18n** &mdash; Multi-language support

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), httpx
- **Frontend:** Jinja2, Chart.js 4.x, vanilla JS
- **Database:** SQLite via aiosqlite
- **Infrastructure:** Docker, Docker Compose

## License

MIT
