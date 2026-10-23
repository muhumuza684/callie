"""Everything the server writes into its home folder is private and must never reach git or a Docker image."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = (ROOT / ".gitignore").read_text().split()
DOCKERIGNORE = (ROOT / ".dockerignore").read_text().split()
PRIVATE = ["session.key", "usage.json", "users/", ".env"]


def test_private_files_are_ignored_by_git():
    for name in PRIVATE:
        assert name in GITIGNORE, name


def test_private_files_stay_out_of_docker_images():
    for name in ("session.key", "usage.json", "users", ".env"):
        assert name in DOCKERIGNORE, name


def test_the_push_script_untracks_them_if_they_were_ever_committed():
    push = (ROOT / "scripts" / "push.ps1").read_text()
    for name in ("session.key", "usage.json", "users"):
        assert name in push.split("$private = @(")[1].split(")")[0], name


def test_every_file_the_server_creates_at_home_is_listed():
    code = "".join(p.read_text() for p in (ROOT / "server").glob("*.py"))
    import re
    for made in set(re.findall(r'config\.HOME / "([\w.]+)"', code)):
        assert made in "".join(GITIGNORE).replace("/", "") + "logs" or made in GITIGNORE or made + "/" in GITIGNORE, made
