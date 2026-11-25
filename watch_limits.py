#!/usr/bin/env python3
"""Post to Discord when Claude Code hits the subscription usage limit.

Runs in the background inside the container. Every 20 seconds it reads the
last lines of the `claude` tmux session; when a usage-limit message appears
there, it posts once to the Discord webhook in DISCORD_WEBHOOK_URL, including
the reset time when Claude Code shows one. It posts again only for a new limit
message (e.g. the next day), not for the same one.

When the limit is over it posts once that reviews are back: when Claude Code
says the limit has reset, or when the limit message is no longer the latest
thing in the pane (Claude has done other work since).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
INTERVAL = 20
STATE = os.path.expanduser("~/.duels-limit-notified")

# Claude Code's wording varies by version; match the common phrasings.
LIMIT_RE = re.compile(
    r"(usage limit|hit your (?:usage |weekly |session )?limit|(?:5-hour|weekly|session) limit|"
    r"limit (?:reached|will reset)|out of (?:extra )?usage)",
    re.IGNORECASE,
)
# a line saying the limit is over, not when it will be
RESET_DONE_RE = re.compile(
    r"(limit|usage)\b[^\n]{0,40}\b(has reset|was reset|is reset|reset now|refreshed|is back|available again)"
    r"|\blimit reset\b(?!s)(?!\s+(?:at|in|on)\b)",
    re.IGNORECASE,
)
RESET_RE = re.compile(
    r"resets?\s+(?:at\s+|in\s+|on\s+)?([0-9][^\n.|·]{0,40}?(?:am|pm|AM|PM|\)|minutes?|hours?|h\b|m\b)(?:\s*\([^)]*\))?)",
    re.IGNORECASE,
)


def find_limit(text: str) -> tuple[str, str | None] | None:
    """Return (the limit line, reset text or None) for the last limit message in the pane.

    None when there is no limit message, or the latest one says the limit has reset.
    """
    hit = None
    for line in text.splitlines():
        if RESET_DONE_RE.search(line):
            hit = None
        elif LIMIT_RE.search(line):
            hit = line.strip()
    if not hit:
        return None
    m = RESET_RE.search(hit)
    if not m:
        # The reset time is sometimes on the next line.
        lines = text.splitlines()
        idx = max(i for i, l in enumerate(lines) if l.strip() == hit)
        for nxt in lines[idx + 1: idx + 3]:
            m = RESET_RE.search(nxt)
            if m:
                break
    return hit, (m.group(1).strip() if m else None)


def message(reset: str | None) -> str:
    when = f"It resets **{reset}**." if reset else "Check back in a little while."
    return (f"⏳ **Claude usage limit reached.** Replay reviews are paused. {when} "
            f"Repost your link after that; anything already reviewed will be reposted for free.")


RESET_MESSAGE = ("✅ **Claude usage limit has reset.** Replay reviews are back on. "
                 "Repost any link that didn't get its review; anything already reviewed will be reposted for free.")


def post(content: str) -> None:
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(WEBHOOK, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "duels-review-limit-watcher"})
    urllib.request.urlopen(req, timeout=15).read()


def pane() -> str:
    try:
        return subprocess.run(["tmux", "capture-pane", "-p", "-t", "claude", "-S", "-150"],
                              capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return ""


def main() -> int:
    if not WEBHOOK:
        print("DISCORD_WEBHOOK_URL not set; usage-limit alerts are off.")
        return 0
    print("Usage-limit watcher running.")
    # state file: "<hash of the last limit line we posted>" plus " limited" while it's in force
    try:
        saved = open(STATE, encoding="utf-8").read().split()
    except OSError:
        saved = []
    last = saved[0] if saved else ""
    limited = len(saved) > 1 and saved[1] == "limited"
    clear = 0  # checks in a row with no limit showing

    def save() -> None:
        with open(STATE, "w", encoding="utf-8") as f:
            f.write(f"{last} limited" if limited else last)

    while True:
        found = find_limit(pane())
        if found:
            clear = 0
            key = hashlib.sha256(found[0].encode()).hexdigest()
            if key != last:
                try:
                    post(message(found[1]))
                    last, limited = key, True
                    save()
                    print(f"Posted usage-limit alert: {found[0]}")
                except Exception as e:  # webhook down or wrong URL: try again next round
                    print(f"Couldn't post usage-limit alert: {e}", file=sys.stderr)
        elif limited:
            clear += 1
            if clear >= 2:  # gone for two checks in a row, so it's not a redraw glitch
                try:
                    post(RESET_MESSAGE)
                    limited, last = False, ""  # the next limit gets its own alert, even if worded the same
                    save()
                    print("Posted usage-limit reset.")
                except Exception as e:
                    print(f"Couldn't post usage-limit reset: {e}", file=sys.stderr)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
