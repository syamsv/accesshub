# AccessHub

AccessHub is a Slack bot that turns Tailscale ACL (for now , features comming) changes into a self-service workflow. 

![Tailscale request modal](docs/images/modal.png)

## Setup

**1. Slack app**

Create a Slack app at `api.slack.com/apps`. OAuth scopes needed:

```
chat:write          # DM admins + requester
commands            # /accesshub_tailscale slash command
im:write            # open DMs to admins
users:read          # resolve user IDs
users:read.email    # resolve email for ACL src
```

Grab **Bot User OAuth Token** (`xoxb-…`) and **Signing Secret** from "Basic Information".

**2. Tailscale**

Generate an API key at `login.tailscale.com/admin/settings/keys` with `write` scope on the policy file. Note your tailnet name (or just use `-`).

**3. `.env`** in the project root:

```env
# slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
ADMIN_SLACK_USER_IDS=U0ASF4919QV,other-admin@your-company.com

# tailscale
TAILNET=-
TAILSCALE_API_KEY=tskey-api-...
TAILSCALE_RESOURCE_TAGS=tag:server

# bot behaviour
ACCESS_DURATION_INTERVAL_IN_MINS=30
CLEANER_INTERVAL_SECONDS=300

# paths (optional; docker-compose volumes already mount these)
SQLITE_PATH=/app/data/accesshub.db
ACL_BACKUP_DIR=/app/backup
```

**4. Build & run**

```sh
pip install -r requirements.txt
python main.py
```

First log lines you should see:

```
slackbot.main: Bolt listening on http://0.0.0.0:3000/slack/events
cleaner.run: [cleaner] starting; interval=300s
main: accesshub ready — bot + cleaner running
```

**5. Expose to Slack**

Slack needs a **public HTTPS URL** pointing to `POST /slack/events`. Three options:

- **Production**: put the container behind an HTTPS reverse proxy (Caddy / nginx / ALB) with a proper TLS cert. Point Slack at `https://<your-host>/slack/events`.
- **Dev on laptop**: `ngrok http 3000` → use the ngrok HTTPS URL.


Then in the Slack app config:
- **Event Subscriptions** → Request URL: `https://.../slack/events` → subscribe to `app_home_opened`.
- **Slash Commands** → create `/accesshub_tailscale` → same URL.
- **Interactivity & Shortcuts** → same URL.
