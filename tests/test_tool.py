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

def test_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "REVIEWS", tmp_path)
    monkeypatch.setattr(t, "fetch_json", lambda rid: t.decode(gz({MATCH_ID: MANIFEST, GAME_ID: GAME}[rid])))
    m = t.fetch_match(MATCH_ID, t.fetch_json)
    out = t.build_prompt_data(m)
    assert "[3/4] REVEALED OPPONENT HAND: Akood et Emuti, Akood et Emuti" in out
    assert "[4/4] T3 SalamanderBeats: You chose Akood et Emuti" in out
    # main(): writes transcript, then reports cache once a review is saved
    t.main([f"https://duels.ink/replay/{MATCH_ID}"])
    assert (tmp_path / f"{MATCH_ID}.transcript.txt").read_text().startswith(f"REPLAY ID: {MATCH_ID}\nREVIEW FROM: SalamanderBeats")
    (tmp_path / f"{MATCH_ID}.md").write_text("saved")
    assert t.main([f"https://duels.ink/replay/{MATCH_ID}"]) == 0
