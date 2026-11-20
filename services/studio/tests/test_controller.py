from concurrent.futures import ThreadPoolExecutor
import copy
import json
import pytest
from woody.controller import Controller, Rejected
from woody.models import ChatCommand


def command(control, text="!camera cam-1", **kwargs):
    return ChatCommand(platform="twitch", message_id=str(control.clock()) + text, user_id="mod", role="moderator", text=text, timestamp=control.clock(), **kwargs)


def test_rotation_visits_all_thirteen_and_skips_hidden_and_offline(control):
    ids = list(control.data["cameras"])
    visited = set()
    for _ in range(13):
        visited.add(control.data["program"]["slots"][0])
        control.now[0] += 180
        control.tick()
    assert visited == set(ids)
    control.hide(ids[1], True)
    control.set_health(ids[2], "offline")
    for _ in range(15):
        control.now[0] += 180
        control.tick()
        slots = control.frame_state()["slots"]
        assert ids[1] not in slots and ids[2] not in slots
        assert len(set(slots)) == len(slots) == 6


def test_switch_swaps_slots_and_resets_timer(control):
    original = control.data["program"]["slots"].copy()
    control.now[0] += 50
    control.switch(original[3])
    assert control.data["program"]["slots"][0] == original[3]
    assert control.data["program"]["slots"][3] == original[0]
    assert control.next_switch == control.clock() + 180


def test_privacy_mask_blocks_every_scene_and_survives_restart(control):
    cid = control.data["program"]["slots"][0]
    control.save_scene({"alias": "saved", "name": "Saved", "layout": "six", "cameras": [cid], "chat_enabled": True})
    control.hide(cid, True)
    assert control.audio_camera() is None
    assert control.frame_state()["slots"][0] is None
    control.apply_scene("saved")
    assert control.frame_state()["slots"] == [None] * 6
    restarted = Controller(control.store)
    restarted.set_health(cid, "online", True)
    assert restarted.data["cameras"][cid]["hidden"]
    assert restarted.audio_camera() is None
    with pytest.raises(Rejected):
        restarted.switch(cid)


def test_sources_encrypted_and_never_in_public_state(control):
    assert "secret@" not in json.dumps(control.state())
    assert "secret@" not in json.dumps(control.store.load())
    assert "secret@" in next(iter(control.sources().values()))


def test_removing_and_reimporting_a_channel_does_not_clear_its_privacy_block(control):
    cid = list(control.data["cameras"])[0]
    control.hide(cid, True)
    control.remove_camera(cid)
    control.add_camera({"channel_id": cid, "alias": "reimported", "chat_enabled": True}, "Reimported", "rtsp://camera/new")
    control.set_health(cid, "online", True)
    assert control.camera(cid)["hidden"] and not control.available(cid)
    control.hide(cid, False)
    assert control.available(cid)


@pytest.mark.parametrize("patch", [{"safe": True}, {"pinned": True}])
def test_bot_cannot_break_operator_lock(control, patch):
    control.set_program(patch)
    before = copy.deepcopy(control.data)
    result = control.chat(command(control))
    assert not result["accepted"]
    assert "vergrendeld" in result["reply"]
    assert control.data == before


def test_bot_roles_staleness_allowlists_and_permanent_mask(control):
    event = command(control)
    assert not control.chat(event.model_copy(update={"role": "viewer"}))["accepted"]
    assert not control.chat(event.model_copy(update={"message_id": "old", "timestamp": 900}))["accepted"]
    cid = list(control.data["cameras"])[1]
    control.patch_camera(cid, {"chat_enabled": False})
    assert not control.chat(event.model_copy(update={"message_id": "not-allowed"}))["accepted"]
    control.patch_camera(cid, {"chat_enabled": True})
    control.hide(cid, True)
    assert not control.chat(event.model_copy(update={"message_id": "hidden"}))["accepted"]


def test_shared_cooldown_and_deduplication(control):
    event = command(control)
    assert control.chat(event)["accepted"]
    assert "Dubbel" in control.chat(event)["reply"]
    other = event.model_copy(update={"platform": "youtube", "message_id": "yt", "user_id": "other"})
    assert not control.chat(other)["accepted"]
    control.now[0] += 11
    assert control.chat(other.model_copy(update={"message_id": "yt2", "timestamp": control.clock()}))["accepted"]
    control.now[0] += 11
    assert not control.chat(other.model_copy(update={"message_id": "yt3", "timestamp": control.clock()}))["accepted"]


def test_concurrent_chat_commands_change_output_once(control):
    events = [command(control).model_copy(update={"message_id": str(i), "user_id": str(i)}) for i in range(30)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(control.chat, events))
    assert sum(r["accepted"] for r in results) == 1


def test_simulator_and_dry_run_never_change_output_or_consume_live_cooldown(control):
    event = command(control)
    before, deadline, revision = copy.deepcopy(control.data), control.next_switch, control.revision
    assert control.chat(event, preview=True)["accepted"]
    assert control.data == before and control.next_switch == deadline and control.revision == revision
    assert control.chat(event)["accepted"]
    control.chat_settings({**control.data["chat"], "dry_run": True})
    before = copy.deepcopy(control.data)
    result = control.chat(command(control, "!camera cam-3"))
    assert result["accepted"] and result["simulated"]
    assert control.data == before


def test_scene_respects_camera_allowlist_and_hidden_mask(control):
    cid = list(control.data["cameras"])[1]
    control.save_scene({"alias": "garden", "name": "Garden", "layout": "six", "cameras": [cid], "chat_enabled": True})
    control.patch_camera(cid, {"chat_enabled": False})
    assert not control.chat(command(control, "!scene garden"))["accepted"]
    control.patch_camera(cid, {"chat_enabled": True})
    control.hide(cid, True)
    assert control.chat(command(control, "!scene garden").model_copy(update={"message_id": "second"}))["accepted"]
    assert control.frame_state()["slots"] == [None] * 6
    assert control.audio_camera() is None


def test_empty_camera_set_and_removal_do_not_duplicate_or_leak(control):
    for cid in list(control.data["cameras"]):
        control.remove_camera(cid)
    control.now[0] += 180
    control.tick()
    assert control.frame_state()["slots"] == []
    assert control.audio_camera() is None


def test_rotation_and_alias_validation_are_atomic(control):
    before = copy.deepcopy(control.data)
    with pytest.raises(Rejected):
        control.rotation({"enabled": True, "interval_seconds": 10, "order": ["unknown"]})
    with pytest.raises(Rejected):
        control.patch_camera(list(control.data["cameras"])[0], {"alias": "cam-1"})
    assert control.data == before
