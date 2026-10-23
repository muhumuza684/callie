"""When the server refuses a call with a reason (daily limit, Luganda off, ...), the person must see that reason, not "The call was interrupted"."""
from pathlib import Path

APP = (Path(__file__).resolve().parent.parent / "client" / "pwa" / "app.js").read_text()


def test_a_refused_call_shows_its_own_message_when_the_connection_closes():
    assert "noticed = m.code" in APP
    assert "toast(noticed ? (NOTICES[noticed] || NOTICES.generic)" in APP
    assert APP.index("toast(noticed ?") < APP.index("The call was interrupted")           # the reason is checked first
