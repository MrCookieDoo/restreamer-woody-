"""Reuse Core channels and provision one ordinary Restreamer program channel."""
import re
import time
from urllib.parse import quote, urlsplit, urlunsplit
import httpx
import jwt
from .controller import Rejected

PROGRAM_ID = "dba994be-cac9-43f4-9d3f-72629c286640"
PROCESS_ID = f"restreamer-ui:ingest:{PROGRAM_ID}"
CHANNEL_PATTERN = re.compile(r"^restreamer-ui:ingest:([a-f0-9-]{36})$")


class Core:
    def __init__(self, address, secret):
        self.address, self.secret = address.rstrip("/"), secret

    def request(self, method, path, **kwargs):
        token = jwt.encode({"sub": "woody-studio", "usefor": "access", "iat": int(time.time()), "exp": int(time.time()) + 60}, self.secret, algorithm="HS256")
        try:
            with httpx.Client(timeout=10, trust_env=False) as client:
                response = client.request(method, self.address + "/api" + path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except httpx.HTTPError:
            # Core errors may include source credentials; never return response bodies.
            raise Rejected("Core is niet bereikbaar of heeft de opdracht geweigerd") from None

    def channels(self):
        processes = self.request("GET", "/v3/process", params={"filter": "metadata,config"})
        result = []
        for process in processes:
            match = CHANNEL_PATTERN.fullmatch(process["id"])
            if not match or match[1] == PROGRAM_ID:
                continue
            meta = process.get("metadata", {}).get("restreamer-ui", {})
            result.append({"channel_id": match[1], "name": meta.get("meta", {}).get("name") or match[1]})
        return result

    def source(self, channel_id):
        if channel_id == PROGRAM_ID:
            raise Rejected("De hoofdstream kan niet als eigen bron worden gebruikt")
        process = self.request("GET", f"/v3/process/restreamer-ui:ingest:{channel_id}")
        meta = process.get("metadata", {}).get("restreamer-ui", {})
        sources = meta.get("sources", [])
        video_source = (meta.get("profiles") or [{}])[0].get("video", {}).get("source", 0)
        if not isinstance(video_source, int) or not 0 <= video_source < len(sources):
            raise Rejected("Dit kanaal heeft geen ondersteunde netwerkvideobron")
        source = sources[video_source]
        if source.get("type") != "network" or source.get("settings", {}).get("mode", "pull") != "pull":
            raise Rejected("Gebruik een netwerkbron in pull-modus voor deze cameramixer")
        inputs = source.get("inputs", [])
        uri = inputs[0].get("address", "") if inputs else source.get("settings", {}).get("address", "")
        parts = urlsplit(uri)
        if parts.scheme not in ("rtsp", "rtsps", "http", "https", "rtmp", "rtmps") or not parts.hostname:
            raise Rejected("Gebruik een RTSP-, RTMP- of HTTP-netwerkbron")
        # Older metadata may keep credentials separately from the generated input.
        settings = source.get("settings", {})
        if settings.get("username") and not parts.username:
            credentials = quote(settings["username"], safe="") + ":" + quote(settings.get("password", ""), safe="")
            uri = urlunsplit((parts.scheme, credentials + "@" + parts.netloc, parts.path, parts.query, parts.fragment))
        return meta.get("meta", {}).get("name") or channel_id, uri

    def provision(self):
        """Create once; never overwrite an existing channel or publication."""
        processes = self.request("GET", "/v3/process", params={"filter": "config,metadata"})
        existing = next((p for p in processes if p["id"] == PROCESS_ID), None)
        if existing:
            metadata = existing.get("metadata", {}).get("restreamer-ui", {})
            if metadata.get("woody_program") and metadata.get("streams"):
                return {"channel_id": PROGRAM_ID, "created": False}
            inputs = existing.get("config", existing).get("input", [])
            if not inputs or "/woody-program" not in inputs[0].get("address", ""):
                raise Rejected("Het vaste hoofdkanaal-ID is al in gebruik door een ander kanaal")
        config = self.request("GET", "/v3/config")
        config = config.get("config", config)
        if not config.get("rtmp", {}).get("enable", False):
            raise Rejected("Schakel eerst de RTMP-server in bij Restreamer Systeeminstellingen")
        app = config.get("rtmp", {}).get("app", "/live").strip("/")
        token = config.get("rtmp", {}).get("token", "")
        uri = f"rtmp://localhost:1935/{app}/woody-program"
        if token:
            uri += "?token=" + quote(token, safe="")
        process = {
            "id": PROCESS_ID, "type": "ffmpeg", "reference": PROGRAM_ID,
            "options": ["-loglevel", "level+info"],
            "input": [{"id": "input_0", "address": uri, "options": []}],
            "output": [{"id": "output_0", "address": f"{{memfs}}/{PROGRAM_ID}.m3u8", "options": [
                "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "-f", "hls", "-hls_time", "2", "-hls_list_size", "6",
                "-hls_flags", "delete_segments+append_list+independent_segments", "-hls_segment_filename", f"{{memfs}}/{PROGRAM_ID}_%05d.ts",
            ], "cleanup": [{"pattern": f"{PROGRAM_ID}_*.ts", "max_files": 12, "max_file_age_seconds": 60, "purge_on_delete": True}]}],
            "autostart": True, "reconnect": True, "reconnect_delay_seconds": 3, "stale_timeout_seconds": 30,
        }
        if not existing:
            self.request("POST", "/v3/process", json=process)
        else:
            uri = inputs[0]["address"]
        streams = [
            {"url": "", "index": 0, "stream": 0, "type": "video", "codec": "h264", "coder": "h264", "width": 1920, "height": 1080, "pix_fmt": "yuv420p", "fps": 25, "bitrate_kbps": 6000},
            {"url": "", "index": 0, "stream": 1, "type": "audio", "codec": "aac", "coder": "aac", "sampling_hz": 48000, "layout": "stereo", "channels": 2, "bitrate_kbps": 128},
        ]
        self.request("PUT", f"/v3/process/{PROCESS_ID}/metadata/restreamer-ui", json={
            "version": "1.14.0", "meta": {"name": "Woody Hoofdstream", "description": "Samengestelde camerastream"},
            "sources": [{"type": "network", "settings": {"mode": "pull", "address": uri}, "inputs": [{"address": uri, "options": []}], "streams": []}],
            "profiles": [{}], "streams": streams, "control": {"hls": {"storage": "memfs", "master_playlist": False}, "process": {"autostart": True, "reconnect": True}},
            "woody_program": True,
        })
        return {"channel_id": PROGRAM_ID, "created": existing is None}
