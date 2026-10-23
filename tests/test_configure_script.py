"""The key script can be run with no questions, and never writes a key anywhere but .env."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PS = (ROOT / "scripts" / "configure.ps1").read_text()


def test_one_line_use_is_supported():
    body = [l for l in PS.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    assert body[0].startswith("param(") and "$Sunbird" in body[0] and "$Groq" in body[0]       # param must come first in a script
    assert PS.index("param(") < PS.index("Set-Location") < PS.index("$Sunbird.Trim()")
    assert 'Set-Setting "SUNBIRD_API_TOKEN"' in PS and 'Set-Setting "GROQ_API_KEY"' in PS


def test_no_real_token_is_shipped_in_the_project():
    import re
    jwt = re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")
    skip = {".venv", "__pycache__", ".git", ".pytest_cache"}
    for f in ROOT.rglob("*"):
        if f.is_file() and not (set(f.parts) & skip) and f.suffix in {".py", ".ps1", ".md", ".html", ".js", ".txt", ".example", ".yml", ".json", ".cmd", ""}:
            text = f.read_text(errors="ignore")
            hits = [m for m in jwt.findall(text) if "aaaaaaaa" not in m and "xxxxxxxx" not in m]
            assert not hits, f"a token is inside {f.relative_to(ROOT)}"
