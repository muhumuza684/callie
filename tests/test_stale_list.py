"""Files removed from the project are listed in scripts/stale.txt, so an update never leaves old copies behind."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STALE = (ROOT / "scripts" / "stale.txt").read_text().split()


def test_the_removed_luganda_settings_test_is_cleaned_up_on_update():
    assert "tests/test_luganda_setup.py" in STALE                  # its old copy broke the v40 build


def test_no_stale_entry_is_something_the_project_still_needs():
    needed = ["server/main.py", "pipeline/runner.py", "client/pwa/app.js", "scripts/start.ps1", "tests/test_desktop.py"]
    assert not [n for n in needed if n in STALE]
