"""Builds docs/guide.html and docs/hosting.html from GUIDE.md and HOSTING.md. Needs pandoc."""
import pathlib
import re
import subprocess

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
CSS = re.search(r"<style>(.*?)</style>", (DOCS / "phone.html").read_text(), re.S).group(1)   # same look as the phone page


def page(md: str, title: str, out: str):
    body = subprocess.run(["pandoc", "-f", "gfm", "-t", "html", "--no-highlight", str(DOCS / md)], capture_output=True, text=True, check=True).stdout
    body = body.replace('href="HOSTING.md"', 'href="hosting.html"').replace('href="GUIDE.md', 'href="guide.html')
    (DOCS / out).write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title><link rel="icon" href="icon.png"><style>{CSS}</style></head>
<body><div class="w"><nav><b><a href="./">Callie</a></b><span><a href="./#download">Download</a> &middot; <a href="guide.html">Guide</a> &middot; <a href="https://github.com/muhumuza684/callie">GitHub</a></span></nav>
{body}</div></body></html>""")


page("GUIDE.md", "Callie guide", "guide.html")
page("HOSTING.md", "Hosting Callie", "hosting.html")
