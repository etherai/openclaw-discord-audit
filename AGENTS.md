# AGENTS.md — Audit Log Pusher Setup Guide

This file provides instructions for AI agents (Clawdbot instances) to set up and configure the Discord Audit Log Pusher.

## What This Does

Streams all Clawdbot session activity into a dedicated Discord audit channel in real time:
- Incoming user messages (forwarded natively)
- Assistant thinking (💭 truncated previews)
- Tool calls (📂 read, 💾 write, ✏️ edit, ⚡ shell, 🔎 search, 🌐 fetch, etc.)
- Tool results (✓ success / ❌ error)
- Outgoing bot replies (forwarded from watched channels)

## Prerequisites

Before setup, verify these are available:

```bash
python3 -c "import requests; print('OK')"
which curl jq
ls ~/.clawdbot/agents/main/sessions/*.jsonl
```

Install missing dependencies:
```bash
pip3 install requests
sudo apt install -y jq curl
```

## Setup Steps

### 1. Create the config file

```bash
cp scripts/audit-config.sample.json scripts/audit-config.json
```

### 2. Configure `scripts/audit-config.json`

Fill in all fields — obtain values from the user:

| Field | How to get it |
|---|---|
| `discord_token` | Ask the user for their Discord bot token |
| `bot_user_id` | The bot's Discord user ID — find via Discord Developer Portal or by checking the bot's profile |
| `audit_channel_id` | Right-click the target audit channel in Discord → Copy Channel ID (Developer Mode must be enabled) |
| `sessions_dir` | Default: `~/.clawdbot/agents/main/sessions` — verify this path exists |
| `watch_channels` | Array of channel IDs where the bot posts replies that should be mirrored to audit |
| `state_file` | Default: `~/.clawdbot/audit-forwarded.json` — any writable path works |
| `poll_interval` | Seconds between outgoing message polls (default: `3`, increase to reduce API usage) |

**Never commit `audit-config.json` — it contains the bot token.** It is gitignored by default.

### 3. Install as a systemd user service (recommended)

```bash
# Edit paths in the service file first
# Replace /home/USER/clawd with the actual workspace path
nano scripts/clawdbot-audit.service

# Install
mkdir -p ~/.config/systemd/user
cp scripts/clawdbot-audit.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now clawdbot-audit

# Verify it's running
systemctl --user status clawdbot-audit
```

For headless servers (keep running after logout):
```bash
loginctl enable-linger $USER
```

### 4. Verify it works

1. Send a message in any Discord channel the bot monitors
2. Check the audit channel — you should see:
   - The user's message forwarded
   - Tool call indicators (📂, ⚡, etc.)
   - The bot's reply forwarded
3. Check service logs if nothing appears:
   ```bash
   journalctl --user -u clawdbot-audit -f
   ```

## Alternative: Run directly (no systemd)

```bash
cd /path/to/scripts
./audit-log-pusher.sh
```

Or backgrounded:
```bash
nohup ./audit-log-pusher.sh >> /tmp/audit-pusher.log 2>&1 &
```

## Troubleshooting

| Problem | Fix |
|---|---|
| No messages in audit channel | Verify `discord_token` and `audit_channel_id` in config. Check bot has `Send Messages` permission. |
| Bot replies not forwarded | Check `bot_user_id` and `watch_channels` are correct. Verify `requests` is installed. |
| `jq: command not found` | `sudo apt install -y jq` |
| Session files not found | Verify `sessions_dir` path. Clawdbot must be running with active sessions. |
| Duplicate messages | Delete the state file and restart: `rm ~/.clawdbot/audit-forwarded.json` |
| Service won't start | Check paths in the `.service` file. Run `journalctl --user -u clawdbot-audit` for errors. |

## File Reference

```
scripts/
├── audit-log-pusher.sh        # Entry point — run this
├── format-log.py              # Formats session events → Discord messages
├── forward-outgoing.py        # Forwards bot replies from watched channels
├── clawdbot-audit.service     # systemd unit file (edit paths before use)
├── audit-config.json          # Your config (gitignored, contains token)
└── audit-config.sample.json   # Config template (copy to audit-config.json)
```
