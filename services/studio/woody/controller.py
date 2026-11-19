"""One authority for UI, scheduler and bot, including permanent privacy masks."""
import copy
import threading
import time
from .models import ChatSettings, Rotation


class Rejected(ValueError):
    pass


class Controller:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock
        self.lock = threading.RLock()
        self.data = store.load() or {
            "cameras": {}, "scenes": {}, "rotation": Rotation().model_dump(),
            "program": {"safe": True, "pinned": False, "layout": "six", "slots": [], "border_color": "#85532d", "border_width": 4},
            "chat": ChatSettings().model_dump(),
        }
        blocked = self.data.setdefault("blocked_camera_ids", [])
        for cid, camera in self.data["cameras"].items():
            if camera["hidden"] and cid not in blocked:
                blocked.append(cid)
        self.health = {}
        self.bots = {}
        self.global_last = 0.0
        self.user_last = {}
        self.next_switch = clock() + self.data["rotation"]["interval_seconds"]
        self.revision = 0

    def changed(self):
        self.store.save(self.data)
        self.revision += 1

    def available(self, camera):
        c = self.data["cameras"].get(camera)
        return bool(c and not c["hidden"] and self.health.get(camera, {}).get("state") == "online")

    def state(self):
        with self.lock:
            data = copy.deepcopy(self.data)
            for cid, camera in data["cameras"].items():
                camera.pop("source", None)
                camera.update(self.health.get(cid, {"state": "connecting", "audio": False}))
            data["program"]["audio_camera"] = self.audio_camera()
            data["program"]["next_switch_in"] = max(0, round(self.next_switch - self.clock()))
            data["bots"] = copy.deepcopy(self.bots)
            data["revision"] = self.revision
            return data

    def sources(self):
        with self.lock:
            return {cid: self.store.decrypt(c["source"]) for cid, c in self.data["cameras"].items()}

    def add_camera(self, settings, name, source):
        with self.lock:
            cid = settings["channel_id"]
            if cid not in self.data["cameras"] and len(self.data["cameras"]) >= 13:
                raise Rejected("Maximaal 13 camera’s")
            self.unique_alias(settings["alias"], cid)
            previous = self.data["cameras"].get(cid, {})
            self.data["cameras"][cid] = {**settings, "name": name[:80], "source": self.store.encrypt(source), "hidden": previous.get("hidden", False) or cid in self.data["blocked_camera_ids"]}
            if cid not in self.data["rotation"]["order"]:
                self.data["rotation"]["order"].append(cid)
            self.changed()

    def unique_alias(self, alias, cid):
        if any(k != cid and c["alias"] == alias for k, c in self.data["cameras"].items()):
            raise Rejected("Deze camera-alias bestaat al")

    def patch_camera(self, cid, patch):
        with self.lock:
            camera = self.camera(cid)
            if "alias" in patch:
                self.unique_alias(patch["alias"], cid)
            camera.update(patch)
            self.changed()

    def camera(self, cid):
        if cid not in self.data["cameras"]:
            raise Rejected("Onbekende camera")
        return self.data["cameras"][cid]

    def remove_camera(self, cid):
        with self.lock:
            self.camera(cid)
            del self.data["cameras"][cid]
            self.health.pop(cid, None)
            self.data["rotation"]["order"] = [c for c in self.data["rotation"]["order"] if c != cid]
            self.data["program"]["slots"] = [None if c == cid else c for c in self.data["program"]["slots"]]
            for scene in self.data["scenes"].values():
                scene["cameras"] = [None if c == cid else c for c in scene["cameras"]]
            self.changed()

    def hide(self, cid, hidden):
        with self.lock:
            self.camera(cid)["hidden"] = hidden
            blocked = self.data["blocked_camera_ids"]
            if hidden and cid not in blocked:
                blocked.append(cid)
            elif not hidden and cid in blocked:
                blocked.remove(cid)
            # Keep the slot assignment; the render mask is enforced on every frame.
            self.changed()

    def set_health(self, cid, state, audio=False):
        with self.lock:
            status = {"state": state, "audio": audio}
            if self.health.get(cid) != status:
                self.health[cid] = status
                self.revision += 1

    def audio_camera(self):
        p = self.data["program"]
        cid = (p["slots"] or [None])[0]
        return cid if not p["safe"] and self.available(cid) else None

    def frame_state(self):
        with self.lock:
            p = copy.deepcopy(self.data["program"])
            p["slots"] = [cid if not p["safe"] and self.available(cid) else None for cid in p["slots"]]
            p["names"] = {cid: c["name"] for cid, c in self.data["cameras"].items()}
            return p

    def set_program(self, patch):
        with self.lock:
            self.data["program"].update(patch)
            if patch.get("safe") is False and not self.data["program"]["slots"]:
                self.fill_round()
            self.reset_timer()
            self.changed()

    def reset_timer(self):
        self.next_switch = self.clock() + self.data["rotation"]["interval_seconds"]

    def switch(self, cid, *, bot=False):
        with self.lock:
            camera = self.camera(cid)
            if not self.available(cid):
                raise Rejected("Camera is verborgen of offline")
            p = self.data["program"]
            if bot and (p["safe"] or p["pinned"]):
                raise Rejected("De regie is vergrendeld")
            if bot and not camera["chat_enabled"]:
                raise Rejected("Camera is niet beschikbaar via chat")
            slots = (p["slots"] + [None] * 6)[:6]
            if cid in slots:
                index = slots.index(cid)
                slots[0], slots[index] = slots[index], slots[0]
            else:
                slots = [cid, *slots[:5]]
            p.update(slots=slots, safe=False)
            self.reset_timer()
            self.changed()

    def fill_round(self, advance=False):
        p = self.data["program"]
        order = [cid for cid in self.data["rotation"]["order"] if self.available(cid)]
        if not order:
            p["slots"] = []
            return
        current = (p["slots"] or [None])[0]
        index = (order.index(current) + int(advance)) % len(order) if current in order else 0
        p["slots"] = (order[index:] + order[:index])[:6]

    def tick(self):
        with self.lock:
            p, r = self.data["program"], self.data["rotation"]
            if r["enabled"] and not p["safe"] and not p["pinned"] and len(p["slots"]) < 6:
                previous = p["slots"].copy()
                self.fill_round()
                if p["slots"] != previous:
                    self.changed()
            if self.clock() >= self.next_switch:
                if r["enabled"] and not p["safe"] and not p["pinned"]:
                    self.fill_round(advance=True)
                    self.changed()
                self.reset_timer()

    def rotation(self, settings):
        with self.lock:
            order = settings["order"]
            if len(set(order)) != len(order) or any(cid not in self.data["cameras"] for cid in order):
                raise Rejected("Ongeldige camerarotatie")
            self.data["rotation"] = settings
            self.reset_timer()
            self.changed()

    def save_scene(self, scene):
        with self.lock:
            cams = [cid for cid in scene["cameras"] if cid is not None]
            if len(set(cams)) != len(cams) or any(cid not in self.data["cameras"] for cid in cams):
                raise Rejected("Scène bevat onbekende of dubbele camera’s")
            self.data["scenes"][scene["alias"]] = scene
            self.changed()

    def apply_scene(self, alias, *, bot=False):
        with self.lock:
            scene = self.data["scenes"].get(alias)
            if not scene:
                raise Rejected("Onbekende scène")
            p = self.data["program"]
            if bot:
                if p["pinned"] or p["safe"] or scene["layout"] == "safe":
                    raise Rejected("De regie is vergrendeld")
                if not scene["chat_enabled"] or any(not self.camera(cid)["chat_enabled"] for cid in scene["cameras"] if cid is not None):
                    raise Rejected("Scène is niet beschikbaar via chat")
            p.update(safe=scene["layout"] == "safe", layout="full" if scene["layout"] == "full" else "six", slots=(scene["cameras"] + [None] * 6)[:6])
            self.reset_timer()
            self.changed()

    def chat_settings(self, settings):
        with self.lock:
            self.data["chat"] = settings
            self.changed()

    def chat(self, message, *, preview=False):
        with self.lock:
            now = self.clock()
            actor = f'{message.platform}:{message.user_id}'
            command = message.text.strip().lower().split()
            action = command[0] if command else ""
            simulated = preview or message.simulate or self.data["chat"]["dry_run"]
            outcome = {"accepted": False, "simulated": simulated, "reply": ""}
            try:
                if abs(now - message.timestamp) > 30:
                    raise Rejected("Verouderd bericht")
                if not simulated and not self.store.claim_message(message.platform, message.message_id, now):
                    raise Rejected("Dubbel bericht")
                if not preview and not self.data["chat"]["enabled"]:
                    raise Rejected("Chatbediening staat uit")
                if action in ("!cameras", "!scenes") and len(command) == 1:
                    items = self.data["cameras"].values() if action == "!cameras" else self.data["scenes"].values()
                    outcome.update(accepted=True, reply=", ".join(c["alias"] for c in items if c["chat_enabled"] and not c.get("hidden", False)) or "Geen beschikbaar")
                    return outcome
                if message.role not in ("moderator", "owner"):
                    raise Rejected("Alleen moderators en de kanaaleigenaar mogen wisselen")
                if len(command) != 2 or action not in ("!camera", "!scene", "!auto"):
                    raise Rejected("Gebruik !camera <alias>, !scene <alias> of !auto on/off")
                p, settings = self.data["program"], self.data["chat"]
                if p["safe"] or p["pinned"]:
                    raise Rejected("De regie is vergrendeld")
                if not simulated:
                    if now - self.global_last < settings["global_cooldown"] or now - self.user_last.get(actor, 0) < settings["user_cooldown"]:
                        raise Rejected("Wacht even voor de volgende chatwissel")
                # Execute against a private copy for the simulator; no output changes or cooldowns.
                original = copy.deepcopy(self.data) if simulated else None
                original_timer, original_revision = self.next_switch, self.revision
                original_changed = self.changed
                if simulated:
                    self.changed = lambda: None
                try:
                    if action == "!camera":
                        cid = next((cid for cid, c in self.data["cameras"].items() if c["alias"] == command[1]), "")
                        self.switch(cid, bot=True)
                    elif action == "!scene":
                        self.apply_scene(command[1], bot=True)
                    else:
                        if command[1] not in ("on", "off"):
                            raise Rejected("Gebruik !auto on/off")
                        self.rotation({**self.data["rotation"], "enabled": command[1] == "on"})
                finally:
                    if simulated:
                        self.data, self.next_switch, self.revision = original, original_timer, original_revision
                        self.changed = original_changed
                if not simulated:
                    self.global_last = now
                    self.user_last[actor] = now
                outcome.update(accepted=True, reply="Simulatie: toegestaan" if simulated else "Uitgevoerd")
            except Rejected as error:
                outcome["reply"] = str(error)
            finally:
                self.store.audit(actor, action, outcome["reply"])
            return outcome
