---
name: audit-log-pusher
description: >
  Real-time Discord audit logging of all Clawdbot session activity. Streams incoming user messages,
  assistant thinking, tool calls (file ops, shell commands, web searches, browser actions), tool results,
  and outgoing bot replies into a designated Discord audit channel with compact, emoji-tagged formatting.
  Use when setting up session observability, debugging Clawdbot behavior across channels, or maintaining
  an activity audit trail. Also use when the user wants to monitor what Clawdbot is doing in real time
  from a single Discord channel.
---

# Audit Log Pusher

Stream all Clawdbot session activity into a Discord audit channel in real time.

## Components

Three scripts work together:

| File | Role |
|---|---|
| `scripts/audit-log-pusher.sh` | Entry point — tails session JSONL files and pipes lines through the formatter |
| `scripts/format-log.py` | Parses JSONL events and posts formatted messages to the audit channel via Discord API |
| `scripts/forward-outgoing.py` | Polls watched channels for bot replies and forwards them to audit (runs as a background subprocess) |
| `scripts/clawdbot-audit.service` | Systemd user service unit file (templatized — edit paths before installing) |

## Setup

### Prerequisites

- Python 3 with `requests` module (`pip install requests`)
- `jq` CLI tool
- `curl` CLI tool
- A Discord bot token with `Send Messages` permission in the audit channel

### Configuration

1. Copy the sample config:

```bash
cp scripts/audit-config.sample.json scripts/audit-config.json
```

2. Fill in `audit-config.json`:

| Field | Description |
|---|---|
| `discord_token` | Discord bot token |
| `bot_user_id` | The bot's Discord user ID (used to identify outgoing messages) |
| `audit_channel_id` | Target channel ID where audit logs are posted |
| `sessions_dir` | Path to Clawdbot session JSONL directory (default: `~/.clawdbot/agents/main/sessions`) |
| `watch_channels` | Array of Discord channel IDs to monitor for outgoing bot messages |
| `state_file` | Path to JSON file tracking which outgoing messages have been forwarded |
| `poll_interval` | Seconds between polls for outgoing messages (default: 3) |

## Usage

### Start

```bash
bash scripts/audit-log-pusher.sh
```

Run in background or via tmux/screen for persistent monitoring:

```bash
nohup bash scripts/audit-log-pusher.sh &
```

### Stop

Kill the main process — it automatically cleans up the outgoing forwarder subprocess:

```bash
kill %1          # if backgrounded in current shell
# or
pkill -f audit-log-pusher.sh
```

### Run as a systemd user service (recommended)

A pre-built unit file is included at `scripts/clawdbot-audit.service`.

1. **Edit the paths** in the unit file — replace `/home/USER/clawd` with your actual workspace path:

```bash
# Open and update WorkingDirectory + ExecStart
nano scripts/clawdbot-audit.service
```

2. **Install the unit**:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/clawdbot-audit.service ~/.config/systemd/user/
systemctl --user daemon-reload
```

3. **Enable and start**:

```bash
systemctl --user enable --now clawdbot-audit
```

4. **Check status / logs**:

```bash
systemctl --user status clawdbot-audit
journalctl --user -u clawdbot-audit -f
```

5. **Stop / disable**:

```bash
systemctl --user stop clawdbot-audit
systemctl --user disable clawdbot-audit
```

> **Note:** User services only run while the user has an active login session.
> To keep it running after logout, enable lingering: `loginctl enable-linger $USER`.

## Output Format

Messages in the audit channel use emoji prefixes for quick scanning:

| Emoji | Meaning |
|---|---|
| 💭 | Assistant thinking (blockquoted, truncated) |
| 📂 | File read |
| 💾 | File write |
| ✏️ | File edit |
| ⚡ | Shell command |
| 🔎 | Web search |
| 🌐 | Web fetch |
| 💬 | Message action or assistant text |
| 🖥️ | Browser action |
| 🧠 | Memory operation |
| 📡 | Session operation |
| 🔧 | Other tool call |
| ✓ | Successful tool result |
| ❌ | Failed tool result |

Incoming user messages are forwarded as Discord message references (quotes).
Outgoing bot replies are forwarded from watched channels to the audit channel.

## Architecture

```
Session JSONL files
       │
       ▼
audit-log-pusher.sh ──tail -F──▶ format-log.py ──▶ Discord audit channel
       │
       └── spawns ──▶ forward-outgoing.py ──▶ polls watched channels
                                              └──▶ forwards bot messages
```

The main script uses `tail -F` to follow all `*.jsonl` files in the sessions directory.
Each line is piped to `format-log.py` which parses the event type and posts a formatted
message to the audit channel. Meanwhile `forward-outgoing.py` runs in the background,
polling watched channels every N seconds and forwarding any bot messages not yet seen.
