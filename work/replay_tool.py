#!/usr/bin/env python3
"""Fetch a duels.ink replay and print a play-numbered transcript for review.

Usage: python3 replay_tool.py <duels.ink replay link>

Standard library only. Prints the transcript and saves it to
reviews/<id>.transcript.txt. If reviews/<id>.md already exists, the first line
says so, so the saved review can be reposted instead of writing a new one.

A link can be a whole match (Bo1/Bo3) or a single game; both are served as
gzipped JSON from https://duels.ink/api/replay/<id>. Each game has `frames`
(one per play; the viewer's "X/N" counter is the frame index) and `logs`;
every frame's `logCountAfter` maps logs onto play numbers.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API = "https://duels.ink/api/replay/{id}"
LINK_RE = re.compile(r"https?://(?:www\.)?duels\.ink/replay/([0-9a-fA-F-]{36})")
REVIEWS = Path(__file__).resolve().parent / "reviews"

NOISE = {
    "TIMER_STARTED", "TIMER_INCREMENT", "TURN_READY", "TURN_SET",
    "TURN_DRAW", "TURN_START",
}


def find_replay_ids(text: str) -> list[str]:
    seen: list[str] = []
    for m in LINK_RE.finditer(text):
        rid = m.group(1).lower()
        if rid not in seen:
            seen.append(rid)
    return seen


def decode(body: bytes) -> dict:
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return json.loads(body)


def fetch_json(replay_id: str) -> dict:
    req = urllib.request.Request(API.format(id=replay_id), headers={"User-Agent": "duels-review"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return decode(r.read())


@dataclass
class Game:
    number: int
    data: dict
    winner: int | None = None
    victory_reason: str | None = None


@dataclass
class Match:
    replay_id: str
    player_names: dict[str, str]
    perspective: int
    match_winner: int | None
    match_format: str | None
    games: list[Game] = field(default_factory=list)


def fetch_match(replay_id: str, fetch=None) -> Match:
    fetch = fetch or fetch_json
    root = fetch(replay_id)
    if root.get("format") == "duels-match-replay-v1":
        match = Match(replay_id, root.get("playerNames", {}), root.get("perspective", 1),
                      root.get("matchWinner"), root.get("matchFormat"))
        for g in root.get("games", []):
            match.games.append(Game(g.get("gameNumber", len(match.games) + 1), fetch(g["replayId"]),
                                    g.get("winner"), g.get("victoryReason")))
    elif root.get("format") == "duels-replay-v1":
        match = Match(replay_id, root.get("playerNames", {}), root.get("perspective", 1),
                      root.get("winner"), "single game")
        match.games.append(Game(1, root, root.get("winner"), root.get("victoryReason")))
    else:
        raise ValueError(f"Unrecognised replay format: {root.get('format')!r}")
    return match


# ---------------------------------------------------------------- parsing

def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def card_reference(data: dict) -> dict[str, str]:
    """fullName -> one-line stats + rules text, for every card object in the replay."""
    cards: dict[str, str] = {}
    for d in _walk(data):
        name = d.get("fullName")
        if not name or "rulesText" not in d or name in cards:
            continue
        kind = d.get("type", "?")
        bits = [kind, f"cost {d.get('cost')}", "inkable" if d.get("inkable") else "uninkable"]
        if kind == "character":
            bits.append(f"{d.get('strength')}/{d.get('willpower')} lore {d.get('lore')}")
        text = (d.get("rulesText") or "").replace("\n", " ").strip()
        cards[name] = f"{', '.join(bits)} | {text}"
    return cards


def _render(log: dict, names: dict[str, str]) -> str:
    msg = log.get("message") or ""
    for i, ref in enumerate(log.get("cardRefs") or []):
        msg = msg.replace("{card:%d}" % i, ref.get("name", "?"))
    msg = re.sub(r"\{player:(\d)\}", lambda m: names.get(m.group(1), m.group(0)), msg)
    return msg


def _reveals(frame: dict) -> list[str]:
    out: list[str] = []
    # Only a whole-hand reveal counts; later patches to single slots are just updates.
    for p in frame.get("patch", []):
        if p.get("path") == "/opponent/revealedHand" and p.get("op") in {"add", "replace"} \
                and isinstance(p.get("value"), list):
            out.extend(c.get("fullName", "?") for c in p["value"] if isinstance(c, dict))
    return out


def transcript(game: Game, names: dict[str, str], perspective: int) -> str:
    data = game.data
    frames = data.get("frames", [])
    logs = data.get("logs", [])
    total = len(frames)
    me = names.get(str(perspective), f"Player {perspective}")
    opp = names.get(str(3 - perspective), f"Player {3 - perspective}")

    # log index -> play number (first frame whose logCountAfter exceeds it)
    after = [f.get("logCountAfter", 0) for f in frames]

    def play_of(i: int) -> int:
        for k, n in enumerate(after):
            if n > i:
                return k + 1
        return total

    first = next((f.get("patch") for f in frames if f.get("actionType") == "CHOOSE_STARTING_PLAYER"), None)
    first_player = None
    for p in first or []:
        if p.get("path") == "/firstPlayer":
            first_player = p.get("value")
    if first_player is None and frames:
        # Otherwise the first player to ink or play goes first.
        for f in frames:
            if f.get("actionType") in {"ADD_TO_INK", "PLAY_CARD"}:
                first_player = f.get("player")
                break

    lines = [
        f"GAME {game.number}: {total} plays. Play numbers below are the replay viewer's counter, written as X/{total}.",
        f"Winner: {names.get(str(game.winner), game.winner)} ({game.victory_reason}).",
        f"On the play: {names.get(str(first_player), first_player)}.",
        f'Log perspective: "You" = {me} (player {perspective}), "Opponent" = {opp}. '
        f"{opp}'s hand and draws are hidden unless revealed.",
        "",
    ]

    last_play_with_reveal = set()
    for i, log in enumerate(logs):
        if log.get("type") in NOISE:
            continue
        play = play_of(i)
        frame = frames[play - 1] if 0 < play <= total else {}
        if play not in last_play_with_reveal:
            rev = _reveals(frame)
            if rev:
                lines.append(f"[{play}/{total}] REVEALED OPPONENT HAND: {', '.join(rev)}")
                last_play_with_reveal.add(play)
        who = names.get(str(log.get("player")), "")
        lines.append(f"[{play}/{total}] T{log.get('turnNumber')} {who}: {_render(log, names)}".rstrip())
    return "\n".join(lines)


def build_prompt_data(match: Match) -> str:
    names = match.player_names
    cards: dict[str, str] = {}
    for g in match.games:
        cards.update(card_reference(g.data))
    parts = [
        f"MATCH {match.replay_id} ({match.match_format}). Players: "
        + ", ".join(f"{v} (player {k})" for k, v in names.items())
        + f". Match winner: {names.get(str(match.match_winner), match.match_winner)}.",
        "",
        "CARD REFERENCE (from the replay's own card data):",
        *[f"- {n}: {t}" for n, t in sorted(cards.items())],
        "",
    ]
    for g in match.games:
        parts.append(transcript(g, names, match.perspective))
        parts.append("")
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    ids = find_replay_ids(" ".join(argv))
    if not ids:
        print("No duels.ink replay link found.", file=sys.stderr)
        return 2
    rid = ids[0]
    REVIEWS.mkdir(exist_ok=True)
    saved = REVIEWS / f"{rid}.md"
    if saved.exists():
        print(f"CACHED REVIEW EXISTS: {saved}")
        return 0
    match = fetch_match(rid)
    data = build_prompt_data(match)
    reviewer = match.player_names.get(str(match.perspective), f"player {match.perspective}")
    header = (f"REPLAY ID: {rid}\nREVIEW FROM: {reviewer} (recorded this replay; their hand is visible)\n"
              f"SAVE REVIEW TO: {saved}\n\n")
    (REVIEWS / f"{rid}.transcript.txt").write_text(header + data, "utf-8")
    print(header + data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
