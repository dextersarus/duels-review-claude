#!/usr/bin/env python3
"""Post update notes to Discord the first time the container starts on a new version.

Reads CHANGELOG.md baked into the image. Compares its newest version with the
last one announced (stored in /work/.announced-version) and posts the notes for
every newer version, oldest first, then records the newest.

Where it posts (first one that's set):
  UPDATES_CHANNEL_ID   a channel ID; posts as the bot, using the token the Discord plugin stores
  DISCORD_WEBHOOK_URL  the usage-limit webhook
On the very first run (nothing announced yet) it posts only the newest version.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

CHANGELOG = Path(os.environ.get("CHANGELOG_FILE", "/opt/CHANGELOG.md"))
STATE = Path(os.environ.get("ANNOUNCED_FILE", "/work/.announced-version"))
ENV_FILE = Path.home() / ".claude" / "channels" / "discord" / ".env"
HEAD_RE = re.compile(r"^##\s+v?(\d+)\.(\d+)\.(\d+)\b(.*)$")
LIMIT = 1900


def parse(text: str) -> list[tuple[tuple[int, int, int], str, str]]:
    """[(version, heading rest, body)] newest first, as written in the file."""
    out, cur = [], None
    for line in text.splitlines():
        m = HEAD_RE.match(line.strip())
        if m:
            cur = [tuple(int(x) for x in m.groups()[:3]), m.group(4).strip(), []]
            out.append(cur)
        elif cur is not None:
            cur[2].append(line)
    return [(v, rest, "\n".join(body).strip()) for v, rest, body in out]


def fmt(v: tuple[int, int, int]) -> str:
    return ".".join(map(str, v))


def pending(entries, last: tuple[int, int, int] | None):
    """Entries to announce, oldest first."""
    if not entries:
        return []
    newest_first = sorted(entries, key=lambda e: e[0], reverse=True)
    if last is None:
        return [newest_first[0]]
    return sorted((e for e in entries if e[0] > last), key=lambda e: e[0])


def message(entries) -> str:
    newest = max(e[0] for e in entries)
    parts = [f"## 🆕 Replay Coach updated to v{fmt(newest)}"]
    for v, rest, body in entries:
        if len(entries) > 1:
            parts.append(f"### v{fmt(v)}")
        parts.append(body)
    return "\n".join(parts)


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    out, cur = [], ""
    for line in text.split("\n"):
        cand = f"{cur}\n{line}" if cur else line
        if len(cand) > limit and cur:
            out.append(cur)
            cur = line[:limit]
        else:
            cur = cand[:limit]
    if cur.strip():
        out.append(cur)
    return out


def bot_token() -> str | None:
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
    return None


def send(content: str) -> None:
    body = {"content": content, "allowed_mentions": {"parse": []}, "flags": 4}  # 4 = no link embeds
    channel = os.environ.get("UPDATES_CHANNEL_ID", "").strip()
    tok = bot_token() if channel else None
    if channel and tok:
        if not re.fullmatch(r"\d{15,22}", channel):
            raise ValueError("UPDATES_CHANNEL_ID must be a Discord channel ID")
        url = f"https://discord.com/api/v10/channels/{channel}/messages"
        headers = {"Authorization": f"Bot {tok}"}
    else:
        url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not url:
            raise RuntimeError("no UPDATES_CHANNEL_ID (with a bot token) or DISCORD_WEBHOOK_URL set")
        headers = {}
    headers.update({"Content-Type": "application/json", "User-Agent": "duels-review (updates, 1.0)"})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    urllib.request.urlopen(req, timeout=15).read()


def main() -> int:
    try:
        entries = parse(CHANGELOG.read_text("utf-8"))
    except OSError:
        print("No CHANGELOG.md in the image; skipping update notes.")
        return 0
    last = None
    try:
        m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", STATE.read_text("utf-8").strip())
        last = tuple(int(x) for x in m.groups()) if m else None
    except OSError:
        pass
    todo = pending(entries, last)
    if not todo:
        return 0
    newest = fmt(max(e[0] for e in todo))
    try:
        for part in chunks(message(todo)):
            send(part)
    except Exception as e:  # don't block startup; try again next start
        print(f"Couldn't post update notes for v{newest}: {e}", file=sys.stderr)
        return 0
    STATE.write_text(newest, "utf-8")
    print(f"Posted update notes for v{newest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
