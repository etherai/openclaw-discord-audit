# Clawdbot Audit Log Pusher

Stream every Clawdbot action — incoming messages, assistant reasoning, tool calls, and outgoing replies — into a dedicated Discord audit channel in real time.

Three scripts work together to give you full visibility into what your Clawdbot agent is doing, across all sessions, without touching the main conversation flow.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Clawdbot Runtime                             │
│                                                                     │
│   session-abc123.jsonl  ──┐                                         │
│   session-def456.jsonl  ──┼── .jsonl session files (append-only)    │
│   session-ghi789.jsonl  ──┘                                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │    audit-log-pusher.sh      │
              │    (main orchestrator)      │
              │                             │
              │  tail -F *.jsonl            │
              │    │                        │
              │    ▼                        │
              │  format-log.py             │
              │  (per-line formatting)      │
              └─────────────┬──────────────┘
                            │
                   Formatted messages
                            │
                            ▼
              ┌─────────────────────────────┐
              │     Discord Audit Channel   │  ◄──── #audit
              │     (all activity lands     │
              │      here)                  │
              └─────────────────────────────┘
                            ▲
                            │
                   Forwarded bot replies
                            │
              ┌─────────────┴──────────────┐
              │   forward-outgoing.py       │
              │   (polls watched channels   │
              │    for bot messages)         │
              │                             │
              │   channel #general ────┐    │
              │   channel #dev ────────┤    │
              │   channel #help ───────┘    │
              └─────────────────────────────┘
```

### Data Flow

1. **Session events** — Clawdbot writes every interaction to `.jsonl` session files. `audit-log-pusher.sh` tails all of them simultaneously and pipes each line through `format-log.py`, which formats it and posts to the audit channel via the Discord API.

2. **Outgoing replies** — Bot replies in watched Discord channels are picked up by `forward-outgoing.py`, which polls those channels every N seconds and uses Discord's native message forwarding (`message_reference` type 1) to mirror them into the audit channel.

---

## Scripts

| Script | Language | Role |
|---|---|---|
| `audit-log-pusher.sh` | Bash | Main orchestrator. Tails all `.jsonl` session files, pipes through the formatter, and spawns the outgoing forwarder as a background process. |
| `format-log.py` | Python 3 | Formats raw session JSON events into compact, icon-coded Discord messages. |
| `forward-outgoing.py` | Python 3 | Polls watched Discord channels for bot-authored messages and forwards them to the audit channel. Maintains a state file to avoid duplicates. |

### Event Formatting (`format-log.py`)

| Event Type | Icon | Example Output |
|---|---|---|
| Incoming Discord message | *(native forward)* | Forwarded via `message_reference` type 1 |
| Assistant thinking | 💭 | `💭 Let me check the configuration files first…` |
| File read | 📂 | `📂 READ → /home/debian/clawd/config.json` |
| File write | 💾 | `💾 WRITE → /tmp/output.txt` |
| File edit | ✏️ | `✏️ EDIT → /home/debian/clawd/scripts/main.py` |
| Shell command | ⚡ | `⚡ $ git status` |
| Web search | 🔎 | `🔎 SEARCH → python requests timeout` |
| Web fetch | 🌐 | `🌐 FETCH → docs.python.org` |
| Message action | 💬 | `💬 MSG.SEND` |
| Browser action | 🖥️ | `🖥️ BROWSER.snapshot` |
| Memory operation | 🧠 | `🧠 MEMORY_SEARCH` |
| Session operation | 📡 | `📡 sessions_list` |
| Other tool call | 🔧 | `🔧 cron` |
| Tool result (success) | ✓ | `✓ done` or `✓ (42 lines)` |
| Tool result (error) | ❌ | `❌ FileNotFoundError: No such file` |
| Text output | 💬 | `💬 Here's what I found…` |

---

## Prerequisites

- **Python 3.6+** with the `requests` library
- **curl** (used by `format-log.py` for Discord API calls)
- **jq** (used by `audit-log-pusher.sh` to parse config)
- **Clawdbot** installed and running (session `.jsonl` files must exist)
- A **Discord bot token** with permissions to read messages and send messages in the audit channel and any watched channels

### Install Python dependency

```bash
pip3 install requests
```

---

## Configuration

All three scripts read from a shared `audit-config.json` file located in the same directory as the scripts.

### Create the config file

```bash
cp audit-config.sample.json audit-config.json
```

### Configuration fields

| Field | Type | Description |
|---|---|---|
| `discord_token` | string | Your Discord bot token (with `Bot` prefix handled automatically). |
| `bot_user_id` | string | The bot's Discord user ID. Used by the outgoing forwarder to identify which messages are from the bot. |
| `audit_channel_id` | string | The Discord channel ID where all audit messages will be posted. |
| `sessions_dir` | string | Path to Clawdbot's session files directory. Default: `/home/debian/.clawdbot/agents/main/sessions` |
| `watch_channels` | string[] | Array of Discord channel IDs to poll for outgoing bot messages. |
| `state_file` | string | Path to the JSON state file that tracks which messages have already been forwarded. Default: `/home/debian/.clawdbot/audit-forwarded.json` |
| `poll_interval` | number | Seconds between polling cycles for the outgoing forwarder. Default: `3` |

### Example `audit-config.json`

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "bot_user_id": "YOUR_BOT_USER_ID",
  "audit_channel_id": "DISCORD_CHANNEL_ID_FOR_AUDIT_LOGS",
  "sessions_dir": "/home/debian/.clawdbot/agents/main/sessions",
  "watch_channels": ["CHANNEL_ID_1", "CHANNEL_ID_2"],
  "state_file": "/home/debian/.clawdbot/audit-forwarded.json",
  "poll_interval": 3
}
```

---

## Setup & Installation

1. **Clone or copy the scripts** into a directory:

   ```bash
   mkdir -p ~/clawd/scripts
   cp audit-log-pusher.sh format-log.py forward-outgoing.py ~/clawd/scripts/
   cp audit-config.sample.json ~/clawd/scripts/audit-config.json
   ```

2. **Make the orchestrator executable:**

   ```bash
   chmod +x ~/clawd/scripts/audit-log-pusher.sh
   ```

3. **Edit the config:**

   ```bash
   nano ~/clawd/scripts/audit-config.json
   ```

   Fill in your Discord bot token, bot user ID, audit channel ID, and any channels you want to watch.

4. **Verify prerequisites:**

   ```bash
   python3 -c "import requests; print('requests OK')"
   which curl jq
   ```

5. **Ensure session files exist:**

   ```bash
   ls /home/debian/.clawdbot/agents/main/sessions/*.jsonl
   ```

---

## Usage

### Run directly

```bash
cd ~/clawd/scripts
./audit-log-pusher.sh
```

The script will:
- Start `forward-outgoing.py` in the background
- Tail all `.jsonl` files in the sessions directory
- Pipe each new event through `format-log.py`
- Post formatted messages to the audit channel

Press `Ctrl+C` to stop (both the tail and the outgoing forwarder will be cleaned up).

### Run in the background

```bash
nohup ~/clawd/scripts/audit-log-pusher.sh >> /var/log/audit-pusher.log 2>&1 &
```

### Running as a systemd service

The tool ships with a `clawdbot-audit.service` unit file for running as a **user-level** systemd service (no `sudo` required).

1. **Create the user systemd directory** (if it doesn't exist):

   ```bash
   mkdir -p ~/.config/systemd/user
   ```

2. **Copy the service file:**

   ```bash
   cp clawdbot-audit.service ~/.config/systemd/user/
   ```

3. **Edit paths if needed** — the unit file uses `%h` (home directory) by default, so it resolves to `~/clawd/scripts/`. If your scripts live elsewhere, update the paths:

   ```bash
   nano ~/.config/systemd/user/clawdbot-audit.service
   ```

   The default unit file:

   ```ini
   [Unit]
   Description=Clawdbot Audit Log Pusher
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   WorkingDirectory=%h/clawd/scripts
   ExecStart=%h/clawd/scripts/audit-log-pusher.sh
   Restart=on-failure
   RestartSec=5
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=default.target
   ```

4. **Enable and start:**

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable clawdbot-audit
   systemctl --user start clawdbot-audit
   ```

5. **Check status and logs:**

   ```bash
   systemctl --user status clawdbot-audit
   journalctl --user -u clawdbot-audit -f
   ```

> **Tip:** User-level services only run while you're logged in, unless you enable lingering: `loginctl enable-linger $USER`. With lingering enabled, the service starts at boot and persists after logout — ideal for a headless server.

---

## Example Output

Here's what the audit channel looks like during a typical interaction:

```
┌──────────────────────────────────────────────────────┐
│ #audit                                                │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📨 [Forwarded message from #general]                 │
│ User: "Can you check if nginx is running?"           │
│                                                      │
│ 💭 The user wants me to check the nginx service      │
│    status. I'll run systemctl…                       │
│                                                      │
│ ⚡ $ systemctl status nginx                           │
│ ✓ `● nginx.service - A high performance…` (12 lines) │
│                                                      │
│ 📂 READ → /etc/nginx/nginx.conf                      │
│ ✓ `worker_processes auto;` (48 lines)                │
│                                                      │
│ 💬 Nginx is running. The config shows 4 worker…      │
│                                                      │
│ 📨 [Forwarded message from #general]                 │
│ Bot: "✅ Nginx is running with 4 worker processes…"  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Incoming user messages** are forwarded natively (Discord's forward feature, preserving the original message context). **Bot replies** are forwarded from the watched channels by the outgoing forwarder. **Everything in between** — thinking, tool calls, results — is formatted inline with contextual icons.

---

## Troubleshooting

### No messages appearing in audit channel

- **Check the bot token** — Ensure `discord_token` in `audit-config.json` is valid and the bot has `Send Messages` permission in the audit channel.
- **Check channel ID** — Verify `audit_channel_id` is correct (enable Developer Mode in Discord → right-click channel → Copy ID).
- **Check session files exist** — Run `ls /home/debian/.clawdbot/agents/main/sessions/*.jsonl` to confirm there are active session files.
- **Check for errors** — Run `audit-log-pusher.sh` in the foreground and look for error messages on stderr.

### Outgoing messages not being forwarded

- **Check `watch_channels`** — Make sure the channel IDs in the array match the channels where the bot posts.
- **Check `bot_user_id`** — The forwarder filters messages by author ID; if this is wrong, no messages will match.
- **Check `requests` is installed** — Run `python3 -c "import requests"`.
- **Check the state file** — If the state file (`audit-forwarded.json`) has grown stale, delete it and restart.

### Duplicate messages in audit channel

- The state file (`audit-forwarded.json`) tracks forwarded message IDs. If you delete it, recently forwarded messages may be re-forwarded on the next poll cycle.
- The state file is automatically pruned to the last 500 entries to prevent unbounded growth.

### High API usage / rate limiting

- Increase `poll_interval` in the config (default is 3 seconds).
- Reduce the number of channels in `watch_channels`.
- Discord rate limits are handled silently; messages may be delayed but won't be lost from the session log side (they're posted via individual `curl` calls).

### `jq` not found

```bash
sudo apt install jq
```

### Format script not producing output

- The formatter silently drops malformed JSON lines and events it doesn't recognize. Check that session files contain valid JSONL by running:

  ```bash
  tail -1 /home/debian/.clawdbot/agents/main/sessions/*.jsonl | python3 -m json.tool
  ```

---

## File Structure

```
scripts/
├── audit-log-pusher.sh          # Main orchestrator (bash)
├── format-log.py                # Event formatter (python)
├── forward-outgoing.py          # Outgoing message forwarder (python)
├── clawdbot-audit.service       # systemd user service unit file
├── audit-config.json            # Your config (gitignored)
├── audit-config.sample.json     # Config template
└── AUDIT-README.md              # This file
```

---

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
