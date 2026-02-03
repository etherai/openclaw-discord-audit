#!/usr/bin/env python3
"""
Clawdbot Audit Formatter v2
Clean, clever activity capture for #audit
Reads configuration from audit-config.json
"""
import json
import sys
import re
import os
import subprocess
from datetime import datetime

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
DISCORD_TOKEN = _config["discord_token"]


def send(content):
    if not content or not content.strip():
        return
    payload = json.dumps({"content": content[:1950]})
    subprocess.run([
        "curl", "-s", "-X", "POST",
        f"https://discord.com/api/v10/channels/{AUDIT_CHANNEL_ID}/messages",
        "-H", f"Authorization: Bot {DISCORD_TOKEN}",
        "-H", "Content-Type: application/json",
        "-d", payload
    ], capture_output=True)

def forward(channel_id, message_id):
    payload = json.dumps({
        "message_reference": {
            "type": 1,
            "channel_id": channel_id,
            "message_id": message_id
        }
    })
    subprocess.run([
        "curl", "-s", "-X", "POST",
        f"https://discord.com/api/v10/channels/{AUDIT_CHANNEL_ID}/messages",
        "-H", f"Authorization: Bot {DISCORD_TOKEN}",
        "-H", "Content-Type: application/json",
        "-d", payload
    ], capture_output=True)

def trunc(s, n=300):
    s = str(s).strip()
    # Clean up newlines for inline display
    s = re.sub(r'\n+', ' ↵ ', s)
    return (s[:n] + "…") if len(s) > n else s

def extract_discord_ids(text):
    ch = re.search(r'channel id:(\d+)', text)
    msg = re.search(r'\[message_id: (\d+)\]', text)
    return (ch.group(1), msg.group(1)) if ch and msg else (None, None)

def format_thinking(think):
    """Format thinking as a subtle aside"""
    think = trunc(think, 250)
    return f">>> 💭 {think}"

def format_tool_call(name, args):
    """Format tool calls as action items"""
    
    # File operations
    if name in ("Read",):
        path = args.get("path", args.get("file_path", "?"))
        return f"📂 `READ` → **{path}**"
    
    if name in ("Write",):
        path = args.get("path", args.get("file_path", "?"))
        return f"💾 `WRITE` → **{path}**"
    
    if name in ("Edit",):
        path = args.get("path", args.get("file_path", "?"))
        return f"✏️ `EDIT` → **{path}**"
    
    # Shell commands
    if name in ("bash", "exec", "Bash"):
        cmd = args.get("command", "")
        # Extract just the interesting part
        cmd_lines = cmd.strip().split('\n')
        if len(cmd_lines) == 1:
            display = trunc(cmd, 150)
        else:
            first = cmd_lines[0][:80]
            display = f"{first}  *(+{len(cmd_lines)-1} lines)*"
        return f"⚡ `$` {display}"
    
    # Web operations
    if name == "web_search":
        q = args.get("query", "?")
        return f"🔎 `SEARCH` → *{trunc(q, 100)}*"
    
    if name == "web_fetch":
        url = args.get("url", "?")
        # Extract domain
        domain = re.search(r'://([^/]+)', url)
        domain = domain.group(1) if domain else url[:50]
        return f"🌐 `FETCH` → **{domain}**"
    
    # Messages
    if name == "message":
        action = args.get("action", "?")
        return f"💬 `MSG.{action.upper()}`"
    
    # Browser
    if name == "browser":
        action = args.get("action", "?")
        return f"🖥️ `BROWSER.{action}`"
    
    # Memory
    if name in ("memory_search", "memory_get"):
        return f"🧠 `{name.upper()}`"
    
    # Sessions
    if "session" in name.lower():
        return f"📡 `{name}`"
    
    # Generic
    return f"🔧 `{name}`"

def format_result(tool_name, content, is_error):
    """Format tool results compactly"""
    # Get result text
    result = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                result = item.get("text", "")
                break
    else:
        result = str(content)
    
    # Success/failure indicator
    icon = "❌" if is_error else "✓"
    
    # Smart result formatting
    result = result.strip()
    
    # Detect common patterns
    if not result:
        return f"{icon}"
    
    if "Successfully" in result or "success" in result.lower():
        # Extract the key info
        match = re.search(r'Successfully (\w+ \d+ \w+ to .+|.{20,60})', result)
        if match:
            return f"✓ *{trunc(match.group(1), 80)}*"
        return f"✓ *done*"
    
    if is_error:
        return f"❌ `{trunc(result, 150)}`"
    
    # Command output - show snippet
    lines = result.split('\n')
    if len(lines) > 3:
        preview = trunc(lines[0], 80)
        return f"✓ `{preview}` *({len(lines)} lines)*"
    
    return f"✓ `{trunc(result, 120)}`"

def process(line, session_short):
    try:
        d = json.loads(line)
        msg = d.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        # Forward incoming Discord messages
        if role == "user" and isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    ch, mid = extract_discord_ids(text)
                    if ch and mid:
                        forward(ch, mid)
                        return
        
        # Handle assistant messages
        if role == "assistant" and isinstance(content, list):
            parts = []
            
            for item in content:
                if not isinstance(item, dict):
                    continue
                
                t = item.get("type", "")
                
                if t == "thinking":
                    think = item.get("thinking", "")
                    if think:
                        parts.append(format_thinking(think))
                
                elif t == "toolCall":
                    name = item.get("name", "?")
                    args = item.get("arguments", {})
                    parts.append(format_tool_call(name, args))
                
                elif t == "text":
                    text = item.get("text", "")
                    if text and "[Discord" not in text:
                        parts.append(f"💬 {trunc(text, 200)}")
            
            if parts:
                send("\n".join(parts))
        
        # Handle tool results
        elif role == "toolResult":
            tool_name = msg.get("toolName", "")
            is_error = msg.get("isError", False)
            result = format_result(tool_name, content, is_error)
            if result:
                send(result)
                
    except:
        pass

if __name__ == "__main__":
    session = sys.argv[1] if len(sys.argv) > 1 else "?"
    for line in sys.stdin:
        if line.strip():
            process(line.strip(), session)
