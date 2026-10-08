"""Shows a QR code for the phone link (saved as a PNG and opened)."""
import os
import sys

import segno

url = sys.argv[1]
path = os.path.join(os.environ.get("TEMP", "."), "callie-qr.png")
segno.make(url, error="m").save(path, scale=10, border=3)
print("QR code opened. Scan it with your phone camera.")
os.startfile(path)
