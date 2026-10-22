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


def test_landing_links_open_real_pages_not_raw_markdown():
    docs = ROOT / "docs"
    assert ".md" not in re.sub(r"https?://\S+", "", LANDING)                     # nothing on the landing page opens raw markdown
    for page in ("guide.html", "phone.html", "hosting.html", "qr.svg"):
        assert (docs / page).exists(), page
    for page in ("guide.html", "phone.html"):
        assert f'href="{page}"' in LANDING, page
    assert 'src="qr.svg"' in LANDING
    assert "## Use it on your phone" in GUIDE and 'id="use-it-on-your-phone"' in (docs / "guide.html").read_text()


def test_guide_page_matches_the_guide():
    """guide.html and hosting.html are built from the markdown files: every heading must be in both."""
    for md, html in (("GUIDE.md", "guide.html"), ("HOSTING.md", "hosting.html")):
        page = re.sub(r"<[^>]+>", "", (ROOT / "docs" / html).read_text())          # text only
        page = " ".join(page.split())
        for h in re.findall(r"^#{1,3} (.+)$", (ROOT / "docs" / md).read_text(), re.M):
            plain = re.sub(r"[`*]", "", h).replace("&", "&amp;").replace(">", "&gt;")
            assert " ".join(plain.split()) in page, f"{html} is out of date: missing '{h}'"


def test_the_qr_code_points_at_the_landing_page():
    svg = (ROOT / "docs" / "qr.svg").read_text()
    assert svg.startswith("<svg") and "QR code" in svg


def test_hosting_files_are_consistent():
    docker = (ROOT / "Dockerfile").read_text()
    assert "USER callie" in docker and "CALLIE_MODE=hosted" in docker and "--proxy-headers" in docker and "HEALTHCHECK" in docker
    compose = (ROOT / "deploy" / "docker-compose.yml").read_text()
    assert "Caddyfile" in compose and "callie_data:/data" in compose
    assert "reverse_proxy callie:8000" in (ROOT / "deploy" / "Caddyfile").read_text()
    env = (ROOT / "deploy" / ".env.example").read_text()
    assert "INVITE_CODES" in env and "DOMAIN" in env
    assert ".env" in (ROOT / ".dockerignore").read_text().split()                # the key never goes into the image
    assert "deploy/.env" in (ROOT / ".gitignore").read_text().split()
    guide = (ROOT / "docs" / "HOSTING.md").read_text()
    assert "docker compose up -d --build" in guide and "INVITE_CODES" in guide


def test_phone_button_uses_one_https_address_and_sharing_points_at_the_landing_page():
    m = re.search(r'const APP_URL = "([^"]*)";', LANDING)
    assert m and (m.group(1) == "" or m.group(1).startswith("https://"))                  # empty until the always-on address exists
    assert 'id="phoneBtn"' in LANDING and 'href="phone.html"' in LANDING                    # the safe default
    assert 'const SITE = "https://muhumuza684.github.io/callie/";' in LANDING and "wa.me/?text=" in LANDING
