# Deploying cc-team-dashboard at dashboard.danknows.org

## Prerequisites

- Python 3.12+
- `cloudflared` CLI installed ([install guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/))
- DNS for `danknows.org` managed by Cloudflare

## 1. Application Setup

```bash
cd ~/projects/cc-team-dashboard
python3 -m virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Environment Configuration

Copy and edit the environment file:

```bash
cp .env.example .env
```

Generate secrets:

```bash
# Flask secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Dashboard API key (for write endpoints)
python3 -c "import secrets; print(secrets.token_hex(16))"
```

Set all required values in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | 64-char hex key for Flask sessions |
| `FLASK_DEBUG` | No | Set to `1` only for local dev (default: `0`) |
| `DASHBOARD_API_KEY` | Recommended | Protects POST endpoints (register, heartbeat, toggle) |
| `SLACK_BOT_TOKEN` | No | `xoxb-...` token for Slack activity feed |
| `SLACK_CHANNELS` | No | Comma-separated Slack channel IDs |
| `GITHUB_TOKEN` | No | GitHub PAT for issue tracking |
| `GITHUB_REPOS` | No | Comma-separated `owner/repo` list |

## 3. Run with Gunicorn

```bash
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app()"
```

### systemd Service (recommended)

Create `/etc/systemd/system/cc-dashboard.service`:

```ini
[Unit]
Description=CC Team Dashboard
After=network.target

[Service]
User=dan
Group=dan
WorkingDirectory=/home/dan/projects/cc-team-dashboard
Environment="PATH=/home/dan/projects/cc-team-dashboard/venv/bin:/usr/bin"
EnvironmentFile=/home/dan/projects/cc-team-dashboard/.env
ExecStart=/home/dan/projects/cc-team-dashboard/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app()"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cc-dashboard
```

## 4. Cloudflare Tunnel

### Authenticate cloudflared

```bash
cloudflared tunnel login
```

### Create the tunnel

```bash
cloudflared tunnel create cc-dashboard
```

### Configure the tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: cc-dashboard
credentials-file: /home/dan/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: dashboard.danknows.org
    service: http://127.0.0.1:5000
  - service: http_status:404
```

### Create DNS record

```bash
cloudflared tunnel route dns cc-dashboard dashboard.danknows.org
```

### Run the tunnel

```bash
cloudflared tunnel run cc-dashboard
```

### systemd Service for cloudflared (recommended)

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

## 5. Verify

```bash
curl https://dashboard.danknows.org/api/agents
```

## 6. API Key Usage

Write endpoints require the `X-API-Key` header when `DASHBOARD_API_KEY` is set:

```bash
curl -X POST https://dashboard.danknows.org/api/agents/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"name": "kat", "role": "backend", "status": "online"}'
```

The heartbeat cron script (`~/agents/shared/heartbeat-cron.sh`) should be updated to include this header.

## Security Notes

- `FLASK_DEBUG` must be `0` in production (default)
- `FLASK_SECRET_KEY` must be a strong random value
- `DASHBOARD_API_KEY` protects all POST endpoints from unauthenticated writes
- Slack messages in the activity feed are automatically sanitized (tokens and hex secrets are redacted)
- The app binds to `127.0.0.1` only — Cloudflare Tunnel handles public access
- Read-only endpoints (GET) are public by design
