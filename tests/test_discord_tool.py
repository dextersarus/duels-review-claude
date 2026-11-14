import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work"))
import discord_tool as d

BOT = "111111111111111111"
CH, MSG = "222222222222222222", "333333333333333333"


def fake_http(author_id, calls):
    def http(method, path, tok):
        calls.append((method, path))
        if path == "/users/@me":
            return {"id": BOT}
        if method == "GET":
            return {"author": {"id": author_id}}
        return None
    return http


def test_deletes_own_message(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    calls = []
    assert d.delete(CH, MSG, fake_http(BOT, calls)) == "Deleted."
    assert ("DELETE", f"/channels/{CH}/messages/{MSG}") in calls


def test_refuses_someone_elses_message(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    calls = []
    assert d.delete(CH, MSG, fake_http("444444444444444444", calls)).startswith("Refused")
    assert not any(m == "DELETE" for m, _ in calls)


def test_refuses_bad_ids():
    assert d.delete("../../users/@me", MSG, lambda *a: None).startswith("Refused")
    assert d.delete(CH, "123; rm -rf /", lambda *a: None).startswith("Refused")


def test_token_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    f = tmp_path / ".env"
    f.write_text('DISCORD_BOT_TOKEN="abc.def"\n')
    monkeypatch.setattr(d, "ENV_FILE", f)
    assert d.token() == "abc.def"
