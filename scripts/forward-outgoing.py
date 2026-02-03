#!/usr/bin/env python3
"""
Forward bot's outgoing messages to #audit
Polls source channels and forwards any bot messages not yet forwarded
Reads configuration from audit-config.json
"""
import json
import time
import os
import sys
import requests

# ── Load config ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "audit-config.json")

try:
    with open(CONFIG_PATH, "r") as _f:
        _config = json.load(_f)
except FileNotFoundError:
    print(f"ERROR: Config file not found: {CONFIG_PATH}", file=sys.stderr)
    print("Copy audit-config.sample.json to audit-config.json and fill in values.", file=sys.stderr)
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"ERROR: Invalid JSON in config: {e}", file=sys.stderr)
    sys.exit(1)

AUDIT_CHANNEL_ID = _config["audit_channel_id"]
BOT_USER_ID = _config["bot_user_id"]
DISCORD_TOKEN = _config["discord_token"]
STATE_FILE = _config["state_file"]
WATCH_CHANNELS = _config["watch_channels"]
POLL_INTERVAL = _config.get("poll_interval", 3)

HEADERS = {
    "Authorization": f"Bot {DISCORD_TOKEN}",
    "Content-Type": "application/json"
}

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"forwarded": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_recent_messages(channel_id, limit=10):
    """Get recent messages from a channel"""
    try:
        resp = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}",
            headers=HEADERS,
            timeout=10
        )
        if resp.ok:
            return resp.json()
    except:
        pass
    return []

def forward_message(source_channel_id, message_id):
    """Forward a message to audit channel"""
    try:
        payload = {
            "message_reference": {
                "type": 1,
                "channel_id": source_channel_id,
                "message_id": message_id
            }
        }
        resp = requests.post(
            f"https://discord.com/api/v10/channels/{AUDIT_CHANNEL_ID}/messages",
            headers=HEADERS,
            json=payload,
            timeout=10
        )
        return resp.ok
    except:
        return False

def main():
    state = load_state()
    forwarded_set = set(state.get("forwarded", []))
    
    # Keep only last 500 to prevent unbounded growth
    if len(forwarded_set) > 500:
        forwarded_set = set(list(forwarded_set)[-500:])
    
    while True:
        try:
            for channel_id in WATCH_CHANNELS:
                messages = get_recent_messages(channel_id, limit=10)
                
                for msg in messages:
                    msg_id = msg.get("id", "")
                    author = msg.get("author", {})
                    author_id = author.get("id", "")
                    
                    # Skip if not from bot or already forwarded or is in audit channel
                    if author_id != BOT_USER_ID:
                        continue
                    if msg_id in forwarded_set:
                        continue
                    if channel_id == AUDIT_CHANNEL_ID:
                        continue
                    
                    # Forward this message
                    if forward_message(channel_id, msg_id):
                        forwarded_set.add(msg_id)
                        state["forwarded"] = list(forwarded_set)
                        save_state(state)
            
        except Exception as e:
            pass
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
