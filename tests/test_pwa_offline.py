"""The installed app must open when the server is asleep, without ever keeping calls, secrets or sign-in pages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SW = (ROOT / "client" / "pwa" / "sw.js").read_text()
APP = (ROOT / "client" / "pwa" / "app.js").read_text()


def test_cache_name_follows_the_version_so_old_copies_are_dropped():
    assert f'const CACHE = "callie-v{(ROOT / "VERSION").read_text().strip()}"' in SW


def test_every_saved_file_exists():
    import re
    for path in re.findall(r'"(/[^"]*\.(?:js|css|json|png))"', SW.split("KEEP_API")[0]):
        assert (ROOT / "client" / "pwa" / path.lstrip("/")).exists(), path


def test_only_get_requests_for_the_app_files_and_contact_list_are_saved():
    assert 'req.method !== "GET"' in SW and 'url.origin !== location.origin' in SW
    assert 'const KEEP_API = ["/api/state"]' in SW
    for never in ("/ws", "/api/ping", "/login", "/setup", "/health"):
        assert never not in SW.split("KEEP_API =")[1].split("\n")[0] and f'"{never}' not in SW.split("const SHELL")[1].split("];")[0]
    assert "res.ok && !res.redirected" in SW                  # no error pages, no sign-in redirects


def test_a_sleeping_server_gets_a_friendly_message():
    assert "Callie is waking up" in APP and "Callie is resting right now" in APP
