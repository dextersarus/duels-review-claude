import gzip
import json
MATCH_ID = "01a1cc4f-fbdf-7e6e-bacc-fde2b926f080"
GAME_ID = "01a1cc4f-fbea-73a7-9532-bd1553e60134"

URSULA = {"id": "9-90", "fullName": "Ursula - Deceiver", "type": "character", "cost": 2, "inkable": True,
          "strength": 1, "willpower": 3, "lore": 1,
          "rulesText": "YOU'LL NEVER EVEN MISS IT When you play this character, chosen opponent reveals their hand and discards a song card of your choice."}
AKOOD = {"id": "x-1", "fullName": "Akood et Emuti", "type": "action", "cost": 3, "inkable": False,
         "strength": None, "willpower": None, "lore": None, "rulesText": "You pay 2 less for the next character you play this turn. Draw a card."}

GAME = {
    "format": "duels-replay-v1", "perspective": 2, "winner": 1, "victoryReason": "concession",
    "playerNames": {"1": "Alber0", "2": "SalamanderBeats"},
    "baseSnapshot": {"myPlayer": {"hand": [URSULA]}},
    "frames": [
        {"seq": 1, "actionType": "CHOOSE_STARTING_PLAYER", "player": 1, "turnNumber": 1, "logCountAfter": 1,
         "patch": [{"op": "replace", "path": "/firstPlayer", "value": 1}]},
        {"seq": 2, "actionType": "ADD_TO_INK", "player": 1, "turnNumber": 1, "logCountAfter": 3, "patch": []},
        {"seq": 3, "actionType": "PLAY_CARD", "player": 2, "turnNumber": 3, "logCountAfter": 5,
         "patch": [{"op": "add", "path": "/opponent/revealedHand", "value": [AKOOD, AKOOD]}]},
        {"seq": 4, "actionType": "RESPOND_TO_PROMPT", "player": 2, "turnNumber": 3, "logCountAfter": 6, "patch": []},
    ],
    "logs": [
        {"turnNumber": 1, "player": None, "type": "GAME_START", "message": "Game started!"},
        {"turnNumber": 1, "player": 1, "type": "TIMER_STARTED", "message": "noise"},
        {"turnNumber": 1, "player": 1, "type": "CARD_INKED", "message": "Opponent added {card:0} to ink",
         "cardRefs": [{"id": "a", "name": "Angel - Siren Singer"}]},
        {"turnNumber": 3, "player": 2, "type": "CARD_PLAYED", "message": "You played {card:0} (cost 2)",
         "cardRefs": [{"id": "9-90", "name": "Ursula - Deceiver"}]},
        {"turnNumber": 3, "player": 2, "type": "TURN_DRAW", "message": "noise"},
        {"turnNumber": 3, "player": 2, "type": "CHOICE_RESOLVED", "message": "You chose {card:0}",
         "cardRefs": [{"id": "x-1", "name": "Akood et Emuti"}]},
    ],
}
MANIFEST = {"format": "duels-match-replay-v1", "perspective": 2, "matchWinner": 1, "matchFormat": "bo3",
            "playerNames": {"1": "Alber0", "2": "SalamanderBeats"},
            "games": [{"gameNumber": 1, "replayId": GAME_ID, "winner": 1, "victoryReason": "concession"}]}


def gz(obj):
    return gzip.compress(json.dumps(obj).encode())



import importlib.util, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import replay_tool as t

EVAL = {"available": True, "perspective": 2, "winProb": [None, 0.5, 0.52, 0.6, 0.2]}


def test_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "REVIEWS", tmp_path)
    monkeypatch.setattr(t, "fetch_json", lambda rid: t.decode(gz(EVAL if rid.endswith("?format=eval") else {MATCH_ID: MANIFEST, GAME_ID: GAME}[rid])))
    m = t.fetch_match(MATCH_ID, t.fetch_json)
    out = t.build_prompt_data(m)
    assert "[3/4] REVEALED OPPONENT HAND: Akood et Emuti, Akood et Emuti" in out
    assert "[4/4] T3 SalamanderBeats: You chose Akood et Emuti   <<win% 60 -> 20>>" in out
    assert "- [4/4] 60% -> 20% (-40): T3 SalamanderBeats: You chose Akood et Emuti" in out
    assert "[3/4]" in out and "<<win% 52" not in out   # +8 is below the 12-point threshold
    # main(): writes transcript, then reports cache once a review is saved
    t.main([f"https://duels.ink/replay/{MATCH_ID}"])
    tr = (tmp_path / f"{MATCH_ID}.transcript.txt").read_text()
    assert tr.startswith(f"REPLAY ID: {MATCH_ID}\nESTIMATE: about 1 minute (1 game, 4 plays)\nREVIEW FROM: SalamanderBeats")
    assert t.main([MATCH_ID.join(["https://duels.ink/replay/", ""]), "--done"]) == 0
    assert (tmp_path / "timings.csv").read_text().splitlines()[1].startswith(f"{MATCH_ID},4,")
    (tmp_path / f"{MATCH_ID}.md").write_text("saved")
    assert t.main([f"https://duels.ink/replay/{MATCH_ID}"]) == 0


def test_estimates():
    assert t.describe(t.estimate_seconds(214, [])) == "about 3 minutes"   # 45 + 0.75*214 = 205s
    hist = [(100, 120.0), (200, 260.0), (150, 150.0)]                     # 1.2, 1.3, 1.0 s/play
    assert t.estimate_seconds(214, hist) == 1.2 * 214
    assert t.describe(20) == "about 1 minute"


def test_eval_missing_is_fine(monkeypatch):
    def boom(rid):
        if rid.endswith("?format=eval"):
            raise OSError("down")
        return t.decode(gz({MATCH_ID: MANIFEST, GAME_ID: GAME}[rid]))
    monkeypatch.setattr(t, "fetch_json", boom)
    out = t.build_prompt_data(t.fetch_match(MATCH_ID))
    assert "WIN PROBABILITY" not in out and "[4/4]" in out


def test_turn_start_snapshots():
    base = {
        "myPlayer": {"hand": [{"fullName": "Aurora - Holding Court"}], "field": [], "inkwell": [],
                     "discard": [], "lore": 0, "inkDrops": 0, "deckCount": 53},
        "opponent": {"handCount": 7, "field": [], "inkwell": [], "discard": [], "lore": 0,
                     "inkDrops": 0, "deckCount": 53},
    }
    chern = {"fullName": "Chernabog - Unnatural Force", "type": "character", "strength": 5,
             "willpower": 4, "lore": 2, "exerted": True, "damage": 1, "justPlayed": True}
    game = {
        "format": "duels-replay-v1", "perspective": 2, "winner": 1, "victoryReason": "concession",
        "playerNames": {"1": "Alber0", "2": "SalamanderBeats"},
        "baseSnapshot": base,
        "frames": [
            {"actionType": "CHOOSE_STARTING_PLAYER", "player": 1, "turnNumber": 1, "logCountAfter": 1,
             "patch": [{"op": "replace", "path": "/firstPlayer", "value": 1}]},
            {"actionType": "PLAY_CARD", "player": 1, "turnNumber": 1, "logCountAfter": 2,
             "patch": [{"op": "add", "path": "/opponent/field/0", "value": chern},
                       {"op": "replace", "path": "/opponent/handCount", "value": 6},
                       {"op": "add", "path": "/opponent/inkwell/0", "value": {"hidden": True, "exerted": True}}]},
            {"actionType": "END_TURN", "player": 1, "turnNumber": 1, "logCountAfter": 3,
             "patch": [{"op": "add", "path": "/myPlayer/hand/1", "value": {"fullName": "Pluto - Friendly Pooch"}},
                       {"op": "add", "path": "/myPlayer/inkwell/0", "value": {"exerted": False}},
                       {"op": "replace", "path": "/myPlayer/inkDrops", "value": 1}]},
            {"actionType": "QUEST", "player": 2, "turnNumber": 1, "logCountAfter": 4, "patch": []},
        ],
        "logs": [
            {"turnNumber": 1, "player": None, "type": "GAME_START", "message": "Game started!"},
            {"turnNumber": 1, "player": 1, "type": "CARD_PLAYED", "message": "Opponent played Chernabog"},
            {"turnNumber": 1, "player": 2, "type": "CARD_DRAWN", "message": "You drew Pluto"},
            {"turnNumber": 1, "player": 2, "type": "CARD_QUEST", "message": "You quested"},
        ],
    }
    match = t.Match("x" * 36, game["playerNames"], 2, 1, "single game", [t.Game(1, game, 1, "concession")])
    out = t.build_prompt_data(match)
    print(out)
    start = out.index("=== TURN START: Alber0's turn T1")
    second = out.index("=== TURN START: SalamanderBeats's turn T1")
    assert start < out.index("Opponent played Chernabog") < out.index("You drew Pluto") < second < out.index("You quested")
    snap = out[second:out.index("You quested")]
    assert "SalamanderBeats: hand (2): Aurora - Holding Court, Pluto - Friendly Pooch | 1 ink (1 ready) + 1 ink drop" in snap
    assert "Alber0: hand 6 cards (hidden) | 1 ink (0 ready)" in snap
    assert "Chernabog - Unnatural Force 5/4 L2 [dmg 1, exerted]" in snap
    assert "drying" not in snap


def test_apply_patch_ops():
    doc = {"a": [1, 2, 3], "b": {"c": 1}}
    t._apply(doc, {"op": "remove", "path": "/a/1"})
    t._apply(doc, {"op": "add", "path": "/a/-", "value": 9})
    t._apply(doc, {"op": "replace", "path": "/b/c", "value": 2})
    t._apply(doc, {"op": "add", "path": "/b/d~1e", "value": True})
    assert doc == {"a": [1, 3, 9], "b": {"c": 2, "d/e": True}}
