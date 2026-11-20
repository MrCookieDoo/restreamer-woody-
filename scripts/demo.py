#!/usr/bin/env python3
"""Register synthetic cameras in an explicitly enabled, isolated demo install."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

settings = dict(line.split("=", 1) for line in (Path(__file__).resolve().parents[1] / ".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line)
if settings.get("WOODY_ALLOW_TEST_SOURCES") != "1":
    raise SystemExit("Enable WOODY_ALLOW_TEST_SOURCES=1 on a separate test install first")
base = "http://localhost:" + settings.get("WOODY_HTTP_PORT", "8080")
payload = json.dumps({"username": settings.get("CORE_API_AUTH_USERNAME", "admin"), "password": settings["CORE_API_AUTH_PASSWORD"]}).encode()
with urlopen(Request(base + "/api/login", data=payload, headers={"Content-Type": "application/json"}), timeout=15) as response:
    token = json.load(response)["access_token"]
with urlopen(Request(base + "/api/woody/v1/demo", data=b"", headers={"Authorization": "Bearer " + token}), timeout=30) as response:
    result = json.load(response)
print(f"Registered {len(result['cameras'])} synthetic cameras. Open Regie; no real cameras were accessed.")
