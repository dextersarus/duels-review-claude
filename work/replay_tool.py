#!/usr/bin/env python3
"""Fetch a duels.ink replay and print a play-numbered transcript for review.

Usage: python3 replay_tool.py <duels.ink replay link>
       python3 replay_tool.py <link> --done     (after posting: records how long the review took)

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
import time
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
    win_prob: list | None = None   # duels.ink engine estimate; index k = after play k


@dataclass
class Match:
    replay_id: str
    player_names: dict[str, str]
    perspective: int
    match_winner: int | None
    match_format: str | None
    games: list[Game] = field(default_factory=list)


def fetch_win_prob(game_replay_id: str) -> list | None:
    """duels.ink's per-play win probability for the perspective player, or None if unavailable."""
    try:
        ev = fetch_json(f"{game_replay_id}?format=eval")
    except Exception:
        return None
    wp = ev.get("winProb") if ev.get("available", True) else None
    return wp if isinstance(wp, list) else None


def fetch_match(replay_id: str, fetch=None, fetch_eval=None) -> Match:
    fetch = fetch or fetch_json
    fetch_eval = fetch_eval or fetch_win_prob
    root = fetch(replay_id)
    if root.get("format") == "duels-match-replay-v1":
        match = Match(replay_id, root.get("playerNames", {}), root.get("perspective", 1),
                      root.get("matchWinner"), root.get("matchFormat"))
        for g in root.get("games", []):
            match.games.append(Game(g.get("gameNumber", len(match.games) + 1), fetch(g["replayId"]),
                                    g.get("winner"), g.get("victoryReason"), fetch_eval(g["replayId"])))
    elif root.get("format") == "duels-replay-v1":
        match = Match(replay_id, root.get("playerNames", {}), root.get("perspective", 1),
                      root.get("winner"), "single game")
        match.games.append(Game(1, root, root.get("winner"), root.get("victoryReason"), fetch_eval(replay_id)))
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


def _apply(doc, patch: dict) -> None:
    """Apply one JSON-patch operation (add / remove / replace) in place."""
    parts = [x.replace("~1", "/").replace("~0", "~") for x in patch.get("path", "").split("/")[1:]]
    if not parts:
        return
    obj = doc
    for key in parts[:-1]:
        if isinstance(obj, list):
            obj = obj[int(key)]
        else:
            obj = obj.setdefault(key, {})
    last, op = parts[-1], patch.get("op")
    if isinstance(obj, list):
        idx = len(obj) if last == "-" else int(last)
        if op == "add":
            obj.insert(idx, patch.get("value"))
        elif op == "remove":
            if idx < len(obj):
                obj.pop(idx)
        elif idx < len(obj):
            obj[idx] = patch.get("value")
        else:
            obj.append(patch.get("value"))
    elif op == "remove":
        obj.pop(last, None)
    else:
        obj[last] = patch.get("value")


def _board(cards: list | None) -> str:
    out = []
    for c in cards or []:
        if not isinstance(c, dict):
            continue
        tags = []
        if c.get("damage"):
            tags.append(f"dmg {c['damage']}")
        if c.get("exerted"):
            tags.append("exerted")
        stats = (f" {c.get('strength')}/{c.get('willpower')} L{c.get('lore')}"
                 if c.get("type") == "character" else "")
        out.append(f"{c.get('fullName', '?')}{stats}" + (f" [{', '.join(tags)}]" if tags else ""))
    return "; ".join(out) or "none"


def _ink(inkwell: list | None, drops) -> str:
    inkwell = inkwell or []
    ready = sum(1 for x in inkwell if isinstance(x, dict)
                and not (x.get("exerted") or (x.get("card") or {}).get("exerted")))
    extra = f" + {drops} ink drop{'s' if drops != 1 else ''}" if drops else ""
    return f"{len(inkwell)} ink ({ready} ready){extra}"


def _names(cards: list | None) -> str:
    return ", ".join(c.get("fullName", "?") for c in cards or [] if isinstance(c, dict)) or "none"


def _snapshot(state: dict, me: str, opp: str, label: str) -> str:
    m, o = state.get("myPlayer", {}), state.get("opponent", {})
    hand = m.get("hand") or []
    lines = [
        f"=== {label} ===",
        f"  {me}: hand ({len(hand)}): {_names(hand)} | {_ink(m.get('inkwell'), m.get('inkDrops'))} | lore {m.get('lore', 0)} | deck {m.get('deckCount', '?')}",
        f"  {me} board: {_board(m.get('field'))}" + (f" | items: {_names(m.get('items'))}" if m.get("items") else ""),
        f"  {me} discard: {_names(m.get('discard'))}",
        f"  {opp}: hand {o.get('handCount', '?')} cards (hidden) | {_ink(o.get('inkwell'), o.get('inkDrops'))} | lore {o.get('lore', 0)} | deck {o.get('deckCount', '?')}",
        f"  {opp} board: {_board(o.get('field'))}" + (f" | items: {_names(o.get('items'))}" if o.get("items") else ""),
        f"  {opp} discard: {_names(o.get('discard'))}",
    ]
    return "\n".join(lines)


def turn_snapshots(game: "Game", names: dict[str, str], perspective: int, first_player) -> dict[int, str]:
    """play number -> board snapshot taken after that play, at the start of each turn."""
    data = game.data
    frames = data.get("frames", [])
    me = names.get(str(perspective), f"Player {perspective}")
    opp = names.get(str(3 - perspective), f"Player {3 - perspective}")
    state = json.loads(json.dumps(data.get("baseSnapshot", {})))
    setup = {"CHOOSE_STARTING_PLAYER", "MULLIGAN"}
    last_setup = max((k for k, f in enumerate(frames) if f.get("actionType") in setup), default=-1)
    out: dict[int, str] = {}
    for k, f in enumerate(frames):
        for p in f.get("patch", []):
            try:
                _apply(state, p)
            except (IndexError, KeyError, ValueError, TypeError, AttributeError):
                pass  # a malformed patch shouldn't stop the transcript
        nxt = None
        if f.get("actionType") == "END_TURN" and f.get("player") in (1, 2):
            nxt, turn = 3 - f["player"], f.get("turnNumber")
        elif k == last_setup and first_player in (1, 2):
            nxt, turn = first_player, 1
        if nxt:
            who = names.get(str(nxt), f"Player {nxt}")
            label = f"TURN START: {who}'s turn T{turn} (state after their draw; what {me} could see)"
            out[k + 1] = _snapshot(state, me, opp, label)
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
        f"=== TURN START === blocks show the board at the start of each turn: exactly what {me} could see then.",
        "",
    ]

    snaps = turn_snapshots(game, names, perspective, first_player)
    pending = sorted(snaps)
    swings = _swings(game.win_prob, total)
    marked: set[int] = set()
    first_text: dict[int, str] = {}
    swing_at = len(lines)
    last_play_with_reveal = set()
    for i, log in enumerate(logs):
        if log.get("type") in NOISE:
            continue
        play = play_of(i)
        while pending and pending[0] < play:
            lines.append(snaps[pending.pop(0)])
        frame = frames[play - 1] if 0 < play <= total else {}
        if play not in last_play_with_reveal:
            rev = _reveals(frame)
            if rev:
                lines.append(f"[{play}/{total}] REVEALED OPPONENT HAND: {', '.join(rev)}")
                last_play_with_reveal.add(play)
        who = names.get(str(log.get("player")), "")
        text = f"T{log.get('turnNumber')} {who}: {_render(log, names)}".rstrip()
        first_text.setdefault(play, text)
        line = f"[{play}/{total}] {text}"
        if play in swings and play not in marked:
            before, after_p = swings[play]
            line += f"   <<win% {before:.0f} -> {after_p:.0f}>>"
            marked.add(play)
        lines.append(line)
    for k in pending:
        lines.append(snaps[k])
    if swings:
        top = sorted(swings.items(), key=lambda kv: -abs(kv[1][1] - kv[1][0]))[:8]
        block = [f"WIN PROBABILITY SWINGS for {me} (duels.ink engine estimate after each play; "
                 f"a pointer to moments worth checking, not proof; it doesn't know about concessions):"]
        for play, (b, a) in sorted(top):
            block.append(f"- [{play}/{total}] {b:.0f}% -> {a:.0f}% ({a - b:+.0f}): {first_text.get(play, '')}")
        lines[swing_at:swing_at] = block + [""]
    return "\n".join(lines)


def _swings(win_prob: list | None, total: int, threshold: float = 0.12) -> dict[int, tuple[float, float]]:
    """play -> (win% before, win% after) for plays that moved the estimate by >= threshold."""
    out: dict[int, tuple[float, float]] = {}
    if not win_prob:
        return out
    prev = None
    for k in range(min(len(win_prob), total + 1)):
        p = win_prob[k]
        if p is None:
            continue
        if prev is not None and k >= 1 and abs(p - prev) >= threshold:
            out[k] = (prev * 100, p * 100)
        prev = p
    return out


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


# Timing: until there's history, assume a fixed start-up cost plus a little per play.
DEFAULT_BASE_S, DEFAULT_PER_PLAY_S = 45.0, 0.75
TIMINGS = "timings.csv"


def estimate_seconds(plays: int, history: list[tuple[int, float]]) -> float:
    """Median seconds-per-play from past reviews, or the default until there are 3 of them."""
    rates = sorted(sec / p for p, sec in history if p > 0 and sec > 0)
    if len(rates) >= 3:
        return rates[len(rates) // 2] * plays
    return DEFAULT_BASE_S + DEFAULT_PER_PLAY_S * plays


def describe(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    return "about 1 minute" if minutes == 1 else f"about {minutes} minutes"


def _history() -> list[tuple[int, float]]:
    rows = []
    try:
        for line in (REVIEWS / TIMINGS).read_text("utf-8").splitlines()[1:]:
            _, plays, sec = line.split(",")
            rows.append((int(plays), float(sec)))
    except (OSError, ValueError):
        pass
    return rows[-50:]


def finish(rid: str) -> int:
    """Record how long a review took (from fetch to now) to improve future estimates."""
    started = REVIEWS / f"{rid}.started"
    try:
        t0, plays = started.read_text("utf-8").split(",")
    except (OSError, ValueError):
        print("No start time recorded for this replay.")
        return 0
    seconds = time.time() - float(t0)
    path = REVIEWS / TIMINGS
    if not path.exists():
        path.write_text("replay_id,plays,seconds\n", "utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{rid},{int(plays)},{seconds:.0f}\n")
    started.unlink(missing_ok=True)
    print(f"Recorded: {seconds:.0f} seconds for {int(plays)} plays.")
    return 0


def main(argv: list[str]) -> int:
    ids = find_replay_ids(" ".join(argv))
    if not ids:
        print("No duels.ink replay link found.", file=sys.stderr)
        return 2
    rid = ids[0]
    REVIEWS.mkdir(exist_ok=True)
    if "--done" in argv:
        return finish(rid)
    saved = REVIEWS / f"{rid}.md"
    if saved.exists():
        print(f"CACHED REVIEW EXISTS: {saved}")
        return 0
    t0 = time.time()
    match = fetch_match(rid)
    data = build_prompt_data(match)
    plays = sum(len(g.data.get("frames", [])) for g in match.games)
    games = len(match.games)
    eta = describe(estimate_seconds(plays, _history()))
    (REVIEWS / f"{rid}.started").write_text(f"{t0},{plays}", "utf-8")
    reviewer = match.player_names.get(str(match.perspective), f"player {match.perspective}")
    header = (f"REPLAY ID: {rid}\n"
              f"ESTIMATE: {eta} ({games} game{'s' if games != 1 else ''}, {plays} plays)\n"
              f"REVIEW FROM: {reviewer} (recorded this replay; their hand is visible)\n"
              f"SAVE REVIEW TO: {saved}\n\n")
    (REVIEWS / f"{rid}.transcript.txt").write_text(header + data, "utf-8")
    print(header + data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
