import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import watch_limits as w


def test_detects_limit_with_reset_time():
    pane = "⏺ Analyzing...\n  ⎿ Claude usage limit reached. Your limit will reset at 9pm (America/Chicago).\n> "
    line, reset = w.find_limit(pane)
    assert "usage limit reached" in line
    assert reset == "9pm (America/Chicago)"


def test_reset_on_next_line():
    pane = "You've hit your session limit\nResets at 11:40 PM\n"
    line, reset = w.find_limit(pane)
    assert line == "You've hit your session limit"
    assert reset == "11:40 PM"


def test_relative_reset():
    _, reset = w.find_limit("5-hour limit reached ∙ resets in 2 hours")
    assert reset == "2 hours"


def test_no_limit_in_normal_output():
    pane = "### Game 1: Loss\n- **24/102:** took Strike; Akood limits their curve. Lore race reached 15.\n"
    assert w.find_limit(pane) is None


def test_message_wording():
    assert "resets **9pm**" in w.message("9pm")
    assert "Check back" in w.message(None)
