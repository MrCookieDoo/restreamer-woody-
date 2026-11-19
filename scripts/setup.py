#!/usr/bin/env python3
"""Create local secrets without printing them or overwriting existing settings."""
import argparse
import base64
import os
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument("--demo", action="store_true", help="Enable synthetic cameras (no real camera access)")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; it has not been changed.")
values = {
    "CORE_API_AUTH_PASSWORD": secrets.token_urlsafe(24),
    "CORE_API_AUTH_JWT_SECRET": secrets.token_urlsafe(48),
    "WOODY_BOT_TOKEN": secrets.token_urlsafe(48),
    "WOODY_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
}
with open(target, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
    for line in (root / ".env.example").read_text().splitlines():
        key = line.split("=", 1)[0]
        if key in values:
            line = key + "=" + values[key]
        if key == "WOODY_ALLOW_TEST_SOURCES" and args.demo:
            line = key + "=1"
        output.write(line + "\n")
print("Created .env (mode 0600). Read the admin password locally; do not share this file.")
