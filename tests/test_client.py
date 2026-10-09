"""Static checks on the web app, so a button without a handler (or a missing element) is caught before release."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PWA = Path(__file__).resolve().parent.parent / "client" / "pwa"
HTML = (PWA / "index.html").read_text()
JS = (PWA / "app.js").read_text()
CSS = (PWA / "style.css").read_text()


def test_every_button_action_has_a_click_handler():
    acts = set(re.findall(r'data-act="([\w-]+)"', HTML + JS))
    missing = sorted(a for a in acts if f'd.act === "{a}"' not in JS)
    assert not missing, f"no click handler for: {missing}"


def test_every_element_the_script_uses_exists():
    used = set(re.findall(r'\$\("([\w-]+)"\)', JS))
    present = set(re.findall(r'id="([\w-]+)"', HTML))
    assert not (used - present), f"script uses ids missing from index.html: {sorted(used - present)}"


def test_clickable_attributes_are_in_the_click_selector():
    selector = re.search(r'closest\("([^"]+)"\)', JS).group(1)
    for attr in set(re.findall(r'\b(data-(?:call|delc|dels|tog|voice|pick|tab))=', HTML + JS)):
        assert f"[{attr}]" in selector, f"{attr} is not handled by the click listener"


def test_every_theme_is_defined_in_css():
    themes = re.findall(r'\["(\w+)", "[A-Za-z ]+", "linear-gradient', JS)
    assert len(themes) >= 5
    for t in themes:
        assert t in ("auto", "midnight") or f"html[data-theme={t}]" in CSS, f"theme {t} has no CSS"


def test_five_ringtones_plus_phone_default():
    names = re.findall(r'^\s{2}(\w+):\s+\{ label: "', JS, flags=re.M)
    assert len(names) == 5
    assert 'value="phone"' in JS


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_javascript_parses():
    r = subprocess.run(["node", "--check", str(PWA / "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_settings_never_opens_the_microphone_by_itself():
    assert "startMicTest()" not in re.search(r'else if \(d\.tab\).*', JS).group(0)
    assert 'data-act="mictest"' in HTML and 'id="micbox"' in HTML      # the test is opt-in and tucked away
