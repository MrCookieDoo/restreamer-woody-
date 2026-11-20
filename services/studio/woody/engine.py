"""Persistent, clocked program output with independent, reconnecting camera pipelines.

The GLib thread owns pipeline mutations; streaming callbacks copy bounded raw
payloads. Each output tick rechecks privacy, including during audio transitions.
"""
from array import array
from collections import deque
import html
import threading
import time


class NullEngine:
    """Explicit control-only mode for API tests; never pretends to send video."""
    def __init__(self, controller, **kwargs):
        self.controller = controller

    def start(self):
        pass

    def stop(self):
        pass

    def status(self):
        return {"mode": "control-only", "state": "disabled", "frames": 0}


class GstEngine:
    def __init__(self, controller, output_uri="", test_output=False, allow_test=False, encoder="x264"):
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst, GLib
        Gst.init(None)
        self.Gst, self.GLib = Gst, GLib
        required = ["compositor", "appsrc", "appsink", "textoverlay", "uridecodebin", "videoconvert", "videoscale", "videorate", "audioconvert", "audioresample"]
        if not test_output:
            encoding = {"x264": "x264enc", "vaapi": "vah264enc", "nvenc": "nvh264enc"}
            if encoder not in encoding:
                raise RuntimeError("Unsupported Woody encoder")
            required += [encoding[encoder], "h264parse", "audiorate", "avenc_aac", "aacparse", "flvmux", "rtmpsink"]
        missing = [name for name in required if not Gst.ElementFactory.find(name)]
        if missing:
            raise RuntimeError("Missing GStreamer plugins: " + ", ".join(missing))
        self.controller = controller
        self.output_uri, self.test_output, self.allow_test = output_uri, test_output, allow_test
        self.encoder = encoder
        self.width, self.height, self.fps = 1280, 720, 25
        self.cameras, self.sources, self.slates = {}, {}, {}
        self.output = None
        self.loop = GLib.MainLoop()
        self.frames = self.audio_frames = self.restarts = 0
        self.started = self.last_frame = 0
        self.output_state = "starting"
        self.previous_audio = None
        self.black = bytes([16]) * (self.width * self.height) + bytes([128]) * (self.width * self.height // 2)
        self.silence = bytes(960 * 2 * 2)
        self.output_retry = 0
        self.stopping = False

    def status(self):
        return {"mode": "gstreamer", "state": self.output_state, "frames": self.frames, "restarts": self.restarts,
                "uptime": round(time.monotonic() - self.started) if self.started else 0,
                "fps": self.fps, "encoder": self.encoder}

    def start(self):
        self.thread = threading.Thread(target=self._run, name="woody-gstreamer", daemon=True)
        self.thread.start()

    def _run(self):
        self.started = time.monotonic()
        self._start_output()
        self._maintenance()
        self.GLib.timeout_add(40, self._video_tick)
        self.GLib.timeout_add(20, self._audio_tick)
        self.GLib.timeout_add(500, self._maintenance)
        self.loop.run()

    def _start_output(self):
        Gst = self.Gst
        if self.output:
            self.output.get_bus().remove_signal_watch()
            self.output.set_state(Gst.State.NULL)
        if self.test_output:
            tail = 'videoconvert ! video/x-raw,format=I420 ! appsink name=probe emit-signals=true max-buffers=1 drop=true sync=false'
            audio_tail = 'appsink name=audio_probe emit-signals=true max-buffers=1 drop=true sync=false'
        else:
            encoders = {
                "x264": "x264enc tune=zerolatency speed-preset=veryfast bitrate=6000 key-int-max=50 bframes=0",
                "vaapi": "vah264enc bitrate=6000 key-int-max=50",
                "nvenc": "nvh264enc bitrate=6000 gop-size=50 bframes=0",
            }
            if self.encoder not in encoders:
                raise RuntimeError("Unsupported video encoder")
            tail = f'videoconvert ! video/x-raw,format=NV12 ! {encoders[self.encoder]} ! h264parse ! queue ! mux. flvmux name=mux streamable=true enforce-increasing-timestamps=false ! rtmpsink name=publish sync=false'
            audio_tail = 'audiorate ! audioconvert ! avenc_aac bitrate=128000 ! aacparse ! queue ! mux.'
        pipeline = ['compositor name=comp background=black max-threads=1 force-live=true latency=40000000 ignore-inactive-pads=true ! video/x-raw,width=1920,height=1080,framerate=25/1 ! ' + tail]
        for i in range(6):
            pipeline.append(f'appsrc name=slot{i} is-live=true format=time block=false max-buffers=2 leaky-type=downstream caps="video/x-raw,format=I420,width=1280,height=720,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive" ! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream ! textoverlay name=label{i} valignment=top halignment=center font-desc="Sans 17" shaded-background=true ! video/x-raw,format=I420 ! comp.sink_{i}')
        pipeline.append('appsrc name=audio is-live=true format=time block=false max-buffers=5 leaky-type=downstream caps="audio/x-raw,format=S16LE,rate=48000,channels=2,layout=interleaved" ! queue max-size-buffers=5 max-size-bytes=0 max-size-time=0 leaky=downstream ! ' + audio_tail)
        pipeline.append('appsrc name=background is-live=true format=time block=false max-buffers=2 leaky-type=downstream caps="video/x-raw,format=I420,width=1920,height=1080,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive" ! comp.sink_6')
        try:
            self.output = Gst.parse_launch(" ".join(pipeline))
            if self.test_output:
                self.output.get_by_name("probe").connect("new-sample", self._probe)
                self.output.get_by_name("audio_probe").connect("new-sample", self._probe_audio)
            else:
                self.output.get_by_name("publish").set_property("location", self.output_uri)
            self.slots = [self.output.get_by_name(f"slot{i}") for i in range(6)]
            self.labels = [self.output.get_by_name(f"label{i}") for i in range(6)]
            self.pads = [self.output.get_by_name("comp").get_static_pad(f"sink_{i}") for i in range(6)]
            self.output.get_by_name("comp").get_static_pad("sink_6").set_property("zorder", 0)
            for pad in self.pads:
                pad.set_property("zorder", 1)
            self.audio = self.output.get_by_name("audio")
            self.background = self.output.get_by_name("background")
            self.background_color = None
            bus = self.output.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._output_message)
            self.video_number = self.audio_number = 0
            self.epoch = time.monotonic()
            self.output.set_state(Gst.State.PLAYING)
            self.output_state = "starting"
        except Exception:
            self.output_state = "error"
            self.output_retry = time.monotonic() + 3

    def _probe(self, sink):
        sample = sink.emit("pull-sample")
        self.last_sample = sample
        return self.Gst.FlowReturn.OK

    def _probe_audio(self, sink):
        sample = sink.emit("pull-sample")
        buffer = sample.get_buffer()
        self.last_audio = buffer.extract_dup(0, buffer.get_size())
        return self.Gst.FlowReturn.OK

    def _output_message(self, bus, message):
        if message.type in (self.Gst.MessageType.ERROR, self.Gst.MessageType.EOS):
            self.output_state = "error"
            self.output_retry = time.monotonic() + 3
        elif message.type == self.Gst.MessageType.STATE_CHANGED and message.src == self.output:
            if message.parse_state_changed()[1] == self.Gst.State.PLAYING:
                self.output_state = "running"

    def _create_camera(self, cid, uri):
        Gst = self.Gst
        self.controller.set_health(cid, "connecting")
        camera = {"pipeline": None, "uri": uri, "frame": None, "last": 0, "since": 0, "started": time.monotonic(),
                  "audio": bytearray(), "audio_last": 0, "lock": threading.RLock(), "retry": 0, "error": False, "reason": ""}
        self.cameras[cid] = camera
        video = 'queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream ! videoconvert ! videoscale add-borders=true ! videorate ! video/x-raw,format=I420,width=1280,height=720,framerate=25/1,pixel-aspect-ratio=1/1,interlace-mode=progressive ! appsink name=frames emit-signals=true max-buffers=1 drop=true sync=true async=false'
        audio = 'queue max-size-buffers=5 max-size-bytes=0 max-size-time=0 leaky=downstream ! audioconvert ! audioresample ! audio/x-raw,format=S16LE,channels=2,rate=48000,layout=interleaved ! appsink name=sound emit-signals=true max-buffers=5 drop=true sync=true async=false'
        try:
            if uri.startswith("test://"):
                if not self.allow_test:
                    raise ValueError("Synthetic sources disabled")
                number = int(uri.split("//")[1]) % 24
                pipeline = Gst.parse_launch(f'videotestsrc is-live=true pattern={number} ! {video} audiotestsrc is-live=true wave=sine freq={220 + number * 30} ! {audio}')
            else:
                pipeline = Gst.Pipeline.new(None)
                decode = Gst.ElementFactory.make("uridecodebin", None)
                decode.set_property("uri", uri)
                decode.connect("source-setup", self._source_setup)
                vbin = Gst.parse_bin_from_description(video, True)
                abin = Gst.parse_bin_from_description(audio, True)
                pipeline.add(decode)
                pipeline.add(vbin)
                pipeline.add(abin)
                def pad_added(element, pad):
                    caps = pad.get_current_caps() or pad.query_caps(None)
                    kind = caps.get_structure(0).get_name()
                    target = vbin if kind.startswith("video/") else abin if kind.startswith("audio/") else None
                    if target and not target.get_static_pad("sink").is_linked():
                        pad.link(target.get_static_pad("sink"))
                decode.connect("pad-added", pad_added)
            camera["pipeline"] = pipeline
            pipeline.get_by_name("frames").connect("new-sample", self._frame, cid)
            pipeline.get_by_name("sound").connect("new-sample", self._sound, cid)
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._camera_message, cid)
            pipeline.set_state(Gst.State.PLAYING)
        except Exception:
            camera["error"] = True
            camera["retry"] = time.monotonic() + 3
            camera["reason"] = "pipeline-error"
            self.controller.set_health(cid, "error", reason=camera["reason"])

    def _source_setup(self, decode, source):
        # RTSP over TCP avoids lost UDP fragments on typical camera networks.
        if source.find_property("protocols"):
            source.set_property("protocols", 4)
        if source.find_property("latency"):
            source.set_property("latency", 200)
        if source.find_property("tcp-timeout"):
            source.set_property("tcp-timeout", 5000000)

    def _frame(self, sink, cid):
        sample = sink.emit("pull-sample")
        camera = self.cameras.get(cid)
        if camera and sample:
            now = time.monotonic()
            with camera["lock"]:
                if now - camera["last"] > 2:
                    camera["since"] = now
                # Pipeline-local GstVideoMeta and pool references must not travel
                # into a different pipeline. Retain only immutable I420 bytes.
                buffer = sample.get_buffer()
                camera["frame"], camera["last"] = buffer.extract_dup(0, buffer.get_size()), now
        return self.Gst.FlowReturn.OK

    def _sound(self, sink, cid):
        sample = sink.emit("pull-sample")
        camera = self.cameras.get(cid)
        if camera and sample:
            buffer = sample.get_buffer()
            with camera["lock"]:
                camera["audio"].extend(buffer.extract_dup(0, buffer.get_size()))
                # At most 200ms; all non-selected camera audio is still drained.
                del camera["audio"][:-38400]
                camera["audio_last"] = time.monotonic()
        return self.Gst.FlowReturn.OK

    def _camera_message(self, bus, message, cid):
        if message.type in (self.Gst.MessageType.ERROR, self.Gst.MessageType.EOS):
            camera = self.cameras.get(cid)
            if camera:
                camera["error"], camera["retry"] = True, time.monotonic() + 3
                camera["reason"] = "stream-ended" if message.type == self.Gst.MessageType.EOS else self._source_error_reason(message)
                self.controller.set_health(cid, "error", reason=camera["reason"])

    def _source_error_reason(self, message):
        # Never expose the raw error/debug strings: they can contain credentials.
        error, debug = message.parse_error()
        if "not-negotiated" in (debug or ""):
            return "format-error"
        if "resource" in error.domain:
            if error.code == int(self.Gst.ResourceError.NOT_AUTHORIZED):
                return "authentication-error"
            if error.code == int(self.Gst.ResourceError.NOT_FOUND):
                return "source-not-found"
            return "connection-error"
        if "stream" in error.domain:
            if error.code == int(self.Gst.StreamError.CODEC_NOT_FOUND):
                return "decoder-missing"
            return "decode-error"
        return "pipeline-error"

    def _maintenance(self):
        if self.stopping:
            return False
        sources = self.controller.sources()
        self.slates = self.controller.store.slate_frames()
        for cid in list(self.cameras):
            camera = self.cameras[cid]
            if cid not in sources or sources[cid] != camera["uri"]:
                self._remove_camera(cid)
        now = time.monotonic()
        for cid, uri in sources.items():
            if cid not in self.cameras:
                self._create_camera(cid, uri)
                continue
            camera = self.cameras[cid]
            with camera["lock"]:
                age = now - camera["last"]
                online = age <= 2 and now - camera["since"] >= 3 and not camera["error"]
                warming = not camera["last"] and now - camera["started"] < 30
                state = "online" if online else "error" if camera["error"] else "connecting" if age <= 2 or warming else "offline"
                reason = camera["reason"] if camera["error"] else "" if online else "waiting-for-frames"
                self.controller.set_health(cid, state, now - camera["audio_last"] < 1, reason=reason)
                # HTTP/HLS sources may need several segments before their first
                # decoded frame. Do not restart them during that initial buffer.
                stalled = age > 8 if camera["last"] else now - camera["started"] > 30
            if (camera["error"] and now >= camera["retry"]) or stalled:
                self._remove_camera(cid)
                self._create_camera(cid, uri)
        if self.output_state == "error" and now >= self.output_retry:
            self.restarts += 1
            self._start_output()
        return True

    def _remove_camera(self, cid):
        camera = self.cameras.pop(cid, None)
        if camera and camera["pipeline"]:
            bus = camera["pipeline"].get_bus()
            bus.remove_signal_watch()
            camera["pipeline"].set_state(self.Gst.State.NULL)

    def _buffer(self, data, number, duration):
        buffer = self.Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = buffer.dts = number * duration
        buffer.duration = duration
        return buffer

    def _running_time(self):
        # PLAYING/preroll may complete after pipeline construction, particularly
        # while camera decoders are starting. Wall time since construction can
        # put frames seconds into the future, delaying a privacy mask or slate.
        clock = self.output.get_clock()
        base = self.output.get_base_time()
        if clock is None or base in (0, self.Gst.CLOCK_TIME_NONE):
            return None
        return max(0, clock.get_time() - base)

    def _video_tick(self):
        if self.stopping:
            return False
        if not self.output or self.output_state == "error":
            return True
        running = self._running_time()
        if running is None:
            return True
        p = self.controller.frame_state()
        positions = [(640, 0, 1280, 720), (0, 0, 640, 360), (0, 360, 640, 360), (0, 720, 640, 360), (640, 720, 640, 360), (1280, 720, 640, 360)]
        now = time.monotonic()
        # Use output-clock timestamps; never inherit unrelated camera clocks.
        number = max(self.video_number, running * self.fps // self.Gst.SECOND)
        duration = self.Gst.SECOND // self.fps
        if self.background_color != p["border_color"]:
            color = int(p["border_color"][1:], 16)
            r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
            y = max(16, min(235, round(16 + .257 * r + .504 * g + .098 * b)))
            u = max(16, min(240, round(128 - .148 * r - .291 * g + .439 * b)))
            v = max(16, min(240, round(128 + .439 * r - .368 * g - .071 * b)))
            self.background_bytes = bytes([y]) * (1920 * 1080) + bytes([u]) * (960 * 540) + bytes([v]) * (960 * 540)
            self.background_color = p["border_color"]
        self.background.emit("push-buffer", self._buffer(self.background_bytes, number, duration))
        for i, appsrc in enumerate(self.slots):
            cid = p["slots"][i] if i < len(p["slots"]) else None
            camera = self.cameras.get(cid)
            frame = None
            if camera:
                with camera["lock"]:
                    if now - camera["last"] <= 2:
                        frame = camera["frame"]
            slate_cid = p["slates"][i] if i < len(p["slates"]) else None
            slate = self.slates.get(slate_cid)
            buffer = self._buffer(frame if frame else slate if slate else self.black, number, duration)
            buffer.pts = buffer.dts = number * duration
            buffer.duration = duration
            appsrc.emit("push-buffer", buffer)
            x, y, w, h = positions[i]
            full = p["safe"] or p["layout"] == "full"
            if full and i == 0:
                x, y, w, h = 0, 0, 1920, 1080
            border = p["border_width"]
            pad = self.pads[i]
            for name, value in (("xpos", x + border), ("ypos", y + border), ("width", w - 2 * border), ("height", h - 2 * border), ("alpha", 0.0 if full and i > 0 else 1.0)):
                if pad.get_property(name) != value:
                    pad.set_property(name, value)
            label = html.escape(p["names"].get(cid, "Wachtbeeld") if frame else "" if slate else "Wachtbeeld")
            if self.labels[i].get_property("text") != label:
                self.labels[i].set_property("text", label)
        self.video_number = number + 1
        self.frames += 1
        self.last_frame = now
        return True

    def _take_audio(self, cid):
        camera = self.cameras.get(cid)
        if not camera:
            return self.silence
        with camera["lock"]:
            if time.monotonic() - camera["audio_last"] > .3:
                return self.silence
            data = bytes(camera["audio"][:len(self.silence)])
            del camera["audio"][:len(self.silence)]
            return data.ljust(len(self.silence), b"\0")

    def _audio_tick(self):
        if self.stopping:
            return False
        if not self.output or self.output_state == "error":
            return True
        running = self._running_time()
        if running is None:
            return True
        target = running * 50 // self.Gst.SECOND
        # GLib callbacks may run late under load. Emit all missing 20ms blocks,
        # rather than handing the AAC encoder a discontinuous sample clock.
        self.audio_number = max(self.audio_number, target - 10)
        while self.audio_number <= target:
            self._audio_block(self.audio_number)
            self.audio_number += 1
        return True

    def _audio_block(self, number):
        with self.controller.lock:
            cid = self.controller.audio_camera()
            data = self._take_audio(cid)
            old = self.previous_audio
            # A blocked camera is never heard in a crossfade, including on reconnect.
            if cid != old and cid is not None:
                previous = self._take_audio(old) if self.controller.available(old) and not self.controller.data["program"]["safe"] else self.silence
                a, b = array("h", previous), array("h", data)
                for i in range(len(b)):
                    factor = (i // 2) / 959
                    b[i] = int(a[i] * (1 - factor) + b[i] * factor)
                data = b.tobytes()
            self.previous_audio = cid
        self.audio.emit("push-buffer", self._buffer(data, number, self.Gst.SECOND // 50))
        self.audio_frames += 1

    def stop(self):
        self.stopping = True
        def shutdown():
            for cid in list(self.cameras):
                self._remove_camera(cid)
            if self.output:
                self.output.set_state(self.Gst.State.NULL)
            self.loop.quit()
            return False
        self.GLib.idle_add(shutdown)
        self.thread.join(timeout=10)
