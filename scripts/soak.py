#!/usr/bin/env python3
"""Observe an already running test broadcast; optionally exercise its switches."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--hours", type=float, default=24)
parser.add_argument("--switches", type=int, default=0, help="Change main camera this many times; use only on a test broadcast")
parser.add_argument("--output", default=".local/soak.json")
args = parser.parse_args()
if args.hours <= 0 or args.switches < 0:
    parser.error("--hours must be positive and --switches cannot be negative")
root = Path(__file__).resolve().parents[1]
env = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line)
base = "http://localhost:" + env.get("WOODY_HTTP_PORT", "8080")
token, expires = "", 0


def call(path, body=None):
    global token, expires
    if time.monotonic() >= expires:
        payload = json.dumps({"username": env.get("CORE_API_AUTH_USERNAME", "admin"), "password": env["CORE_API_AUTH_PASSWORD"]}).encode()
        with urlopen(Request(base + "/api/login", data=payload, headers={"Content-Type": "application/json"}), timeout=15) as response:
            token = json.load(response)["access_token"]
        expires = time.monotonic() + 480
    request = Request(base + "/api/woody/v1" + path, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request, timeout=15) as response:
        return json.load(response)


samples, failures, switches = [], [], 0
deadline = time.monotonic() + args.hours * 3600
initial = call("/state")
last_frames = initial["engine"]["frames"]
restarts = initial["engine"].get("restarts", 0)
try:
    while time.monotonic() < deadline:
        current = call("/state")
        engine = current["engine"]
        if samples and (engine["state"] != "running" or engine["frames"] <= last_frames or engine.get("restarts", 0) != restarts):
            failures.append({"at": time.time(), "reason": "Output stopped, stalled or restarted"})
        last_frames = engine["frames"]
        samples.append({"at": time.time(), "engine": engine, "online": sum(c["state"] == "online" for c in current["cameras"].values())})
        eligible = [cid for cid, c in current["cameras"].items() if c["state"] == "online" and not c["hidden"]]
        if switches < args.switches and eligible:
            call("/program/switch", {"camera": eligible[switches % len(eligible)]})
            switches += 1
        time.sleep(5)
except KeyboardInterrupt:
    failures.append({"at": time.time(), "reason": "Test interrupted before completion"})
except Exception:
    failures.append({"at": time.time(), "reason": "Test endpoint unavailable"})
finally:
    if switches < args.switches:
        failures.append({"at": time.time(), "reason": "Not all requested switches completed"})
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"samples": samples, "failures": failures, "switches": switches}, indent=2))
print(f"Saved {len(samples)} samples, {switches} switches and {len(failures)} failures to {args.output}")
raise SystemExit(1 if failures else 0)
