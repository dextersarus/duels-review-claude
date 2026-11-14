#!/usr/bin/env python3
"""Delete one of the bot's own Discord messages (the official plugin has no delete tool).

Usage: python3 discord_tool.py delete <channel_id> <message_id>

Reads the bot token from DISCORD_BOT_TOKEN or ~/.claude/channels/discord/.env,
so the token never passes through Claude. Refuses to delete messages the bot
didn't write. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://discord.com/api/v10"
ID_RE = re.compile(r"^\d{15,22}$")
ENV_FILE = Path.home() / ".claude" / "channels" / "discord" / ".env"


def token() -> str:
    tok = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if tok:
        return tok
    try:
        for line in ENV_FILE.read_text("utf-8").splitlines():
            key, _, val = line.partition("=")
            if key.strip() == "DISCORD_BOT_TOKEN":
                return val.strip().strip('"').strip("'")
    except OSError:
        pass
    raise SystemExit("No Discord bot token found.")


def call(method: str, path: str, tok: str):
    req = urllib.request.Request(API + path, method=method, headers={
        "Authorization": f"Bot {tok}", "User-Agent": "duels-review (discord_tool, 1.0)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read()
    return json.loads(body) if body else None


def delete(channel_id: str, message_id: str, http=call) -> str:
    if not (ID_RE.match(channel_id) and ID_RE.match(message_id)):
        return "Refused: channel and message IDs must be Discord numeric IDs."
    tok = token()
    me = http("GET", "/users/@me", tok)
    msg = http("GET", f"/channels/{channel_id}/messages/{message_id}", tok)
    if (msg.get("author") or {}).get("id") != me.get("id"):
        return "Refused: that message wasn't sent by this bot."
    http("DELETE", f"/channels/{channel_id}/messages/{message_id}", tok)
    return "Deleted."


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "delete":
        print(__doc__.strip().splitlines()[2])
        return 2
    try:
        print(delete(argv[1], argv[2]))
        return 0
    except urllib.error.HTTPError as e:
        print(f"Discord API error {e.code}: {e.reason}")
        return 1
    except urllib.error.URLError as e:
        print(f"Couldn't reach Discord: {e.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
