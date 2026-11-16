import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import announce_update as a

LOG = """# Update notes
intro
## 1.2.0 (2026-11-16)
- threads
## 1.1.0 (2026-11-13)
- estimates
## 1.0.0 (2026-11-13)
- first
"""


def test_parse_and_pending():
    e = a.parse(LOG)
    assert [x[0] for x in e] == [(1, 2, 0), (1, 1, 0), (1, 0, 0)]
    assert [x[0] for x in a.pending(e, (1, 0, 0))] == [(1, 1, 0), (1, 2, 0)]   # oldest first
    assert a.pending(e, (1, 2, 0)) == []
    assert [x[0] for x in a.pending(e, None)] == [(1, 2, 0)]                     # first run: newest only


def test_message():
    e = a.parse(LOG)
    one = a.message(a.pending(e, (1, 1, 0)))
    assert one.startswith("## 🆕 Replay Coach updated to v1.2.0\n- threads")
    two = a.message(a.pending(e, (1, 0, 0)))
    assert "### v1.1.0\n- estimates" in two and "### v1.2.0\n- threads" in two


def test_main_records_version(tmp_path, monkeypatch):
    (tmp_path / "CHANGELOG.md").write_text(LOG)
    monkeypatch.setattr(a, "CHANGELOG", tmp_path / "CHANGELOG.md")
    monkeypatch.setattr(a, "STATE", tmp_path / "announced")
    (tmp_path / "announced").write_text("1.1.0")
    sent = []
    monkeypatch.setattr(a, "send", sent.append)
    a.main()
    assert len(sent) == 1 and "v1.2.0" in sent[0]
    assert (tmp_path / "announced").read_text() == "1.2.0"
    sent.clear(); a.main()
    assert sent == []          # nothing new: nothing posted


def test_failure_does_not_record(tmp_path, monkeypatch):
    (tmp_path / "CHANGELOG.md").write_text(LOG)
    monkeypatch.setattr(a, "CHANGELOG", tmp_path / "CHANGELOG.md")
    monkeypatch.setattr(a, "STATE", tmp_path / "announced")
    def boom(_):
        raise OSError("offline")
    monkeypatch.setattr(a, "send", boom)
    a.main()
    assert not (tmp_path / "announced").exists()   # retried on next start


def test_real_changelog_parses():
    e = a.parse((Path(__file__).resolve().parents[1] / "CHANGELOG.md").read_text())
    assert e and e[0][0] == max(x[0] for x in e)    # newest first in the file
    assert all(body for _, _, body in e)
