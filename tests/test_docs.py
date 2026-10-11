"""The documentation, landing page and release workflow must agree with each other and with the repository."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
GUIDE = (ROOT / "docs" / "GUIDE.md").read_text()
LANDING = (ROOT / "docs" / "index.html").read_text()
WORKFLOW = (ROOT / ".github" / "workflows" / "build.yml").read_text()


def test_landing_download_links_match_what_the_workflow_builds():
    assets = re.findall(r"asset: (Callie-[\w.]+)", WORKFLOW)
    assert len(assets) == 3
    for a in assets:
        name = a if a.endswith(".exe") else a + ".tar.gz"
        assert f"releases/latest/download/{name}" in LANDING, name
        assert f"releases/latest/download/{name}" in README, name


def test_workflow_tests_then_builds_then_releases():
    d = yaml.safe_load(WORKFLOW)
    assert d["jobs"]["build"]["needs"] == "test" and d["jobs"]["release"]["needs"] == "build"
    assert d["jobs"]["release"]["permissions"]["contents"] == "write"


def test_hero_image_exists_and_is_used():
    root = ET.parse(ROOT / "docs" / "hero.svg").getroot()
    assert root.tag.endswith("svg")
    assert (ROOT / "docs" / "hero.png").read_bytes()[:4] == b"\x89PNG"
    assert "docs/hero.png" in README and "hero.png" in LANDING


def test_docs_do_not_mention_removed_parts():
    for gone in ("stt/", "tts/", "vad/", "requirements-ai", "requirements-audio", "audio.lab"):
        assert gone not in README and gone not in GUIDE, gone


def test_stale_list_matches_the_repository():
    for line in (ROOT / "scripts" / "stale.txt").read_text().split():
        assert not (ROOT / line).exists(), f"{line} is listed as stale but still exists"


def test_secrets_and_build_output_are_never_committed():
    ignore = (ROOT / ".gitignore").read_text().split()
    for must in (".env", "data/store.json", "data/memory.json", "tools/", "dist/", "build/", ".venv/"):
        assert must in ignore, must


def test_packaging_recipe_bundles_the_web_files_and_version():
    spec = (ROOT / "callie.spec").read_text()
    assert "client/pwa" in spec and "VERSION" in spec and "desktop/main.py" in spec


def test_guide_anchor_used_by_the_landing_page_exists():
    assert "## Use it on your phone" in GUIDE and "GUIDE.md#use-it-on-your-phone" in LANDING
