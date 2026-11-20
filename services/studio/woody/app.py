"""Authenticated same-origin Studio API. Core remains the authentication issuer."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hmac
import json
import os
import time
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import jwt
from .controller import Controller, Rejected
from .core import Core, PROGRAM_ID
from .models import CameraSettings, CameraPatch, ChatCommand, ChatSettings, Hidden, ProgramPatch, Rotation, Scene, Switch, BotStatus
from .storage import Store


@dataclass
class Settings:
    database: str
    encryption_key: str
    jwt_secret: str
    bot_token: str
    core_url: str = "http://core:8080"
    engine: str = "gstreamer"
    output_uri: str = "rtmp://core:1935/live/woody-program"
    allow_test: bool = False
    test_output: bool = False
    encoder: str = "x264"

    @classmethod
    def from_env(cls):
        raw_secret = os.environ["CORE_API_AUTH_JWT_SECRET"]
        username = os.getenv("CORE_API_AUTH_USERNAME", "admin")
        password = os.environ["CORE_API_AUTH_PASSWORD"]
        # Core 16.16.0 app/api/api.go derives its actual HS256 signing key this way.
        # A token signed with only the configured JWT secret is not a Core token.
        signing_key = username + password + raw_secret
        settings = cls(
            database=os.getenv("WOODY_DATABASE", "/data/studio.sqlite"),
            encryption_key=os.environ["WOODY_ENCRYPTION_KEY"], jwt_secret=signing_key,
            bot_token=os.environ["WOODY_BOT_TOKEN"], core_url=os.getenv("WOODY_CORE_URL", "http://core:8080"),
            engine=os.getenv("WOODY_ENGINE", "gstreamer"), output_uri=os.getenv("WOODY_OUTPUT_URI", "rtmp://core:1935/live/woody-program"),
            allow_test=os.getenv("WOODY_ALLOW_TEST_SOURCES") == "1", test_output=os.getenv("WOODY_TEST_OUTPUT") == "1",
            encoder=os.getenv("WOODY_ENCODER", "x264"),
        )
        if not username or not password or len(raw_secret) < 32 or len(settings.bot_token) < 32 or hmac.compare_digest(raw_secret, settings.bot_token):
            raise RuntimeError("Separate JWT and bot secrets of at least 32 characters are required")
        return settings


def create_app(settings=None, *, engine_factory=None, core_factory=Core):
    settings = settings or Settings.from_env()
    store = Store(settings.database, settings.encryption_key)
    controller = Controller(store)
    core = core_factory(settings.core_url, settings.jwt_secret)
    if engine_factory is None:
        from .engine import GstEngine, NullEngine
        if settings.engine not in ("gstreamer", "control-only"):
            raise RuntimeError("Unsupported engine")
        engine_factory = GstEngine if settings.engine == "gstreamer" else NullEngine
    engine = engine_factory(controller, output_uri=settings.output_uri, test_output=settings.test_output, allow_test=settings.allow_test, encoder=settings.encoder)

    @asynccontextmanager
    async def lifespan(app):
        engine.start()
        async def scheduler():
            while True:
                await asyncio.sleep(.5)
                controller.tick()
        task = asyncio.create_task(scheduler())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        engine.stop()
        store.close()

    app = FastAPI(title="Woody Studio", version="0.1.0", lifespan=lifespan, docs_url="/api/woody/v1/docs", openapi_url="/api/woody/v1/openapi.json")
    app.state.controller, app.state.engine, app.state.store = controller, engine, store

    def bearer(request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Login vereist")
        return authorization[7:]

    def admin(request: Request):
        try:
            claims = jwt.decode(bearer(request), settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "usefor"]})
            if claims["usefor"] != "access":
                raise jwt.InvalidTokenError()
            return claims
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Ongeldig of verlopen Core-toegangstoken") from None

    def bot(request: Request):
        if not hmac.compare_digest(bearer(request), settings.bot_token):
            raise HTTPException(401, "Ongeldige bot-sleutel")

    @app.exception_handler(Rejected)
    async def rejected(request, error):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    prefix = "/api/woody/v1"

    @app.get("/healthz")
    def health():
        return {"ok": True, "engine": engine.status()["state"]}

    def studio_state():
        # Mutations must have the same envelope as polling. The UI renders these
        # responses immediately, before the next /state request completes.
        return {**controller.state(), "engine": engine.status(), "program_channel_id": PROGRAM_ID}

    @app.get(prefix + "/state", dependencies=[Depends(admin)])
    def state():
        return studio_state()

    @app.get(prefix + "/events")
    async def events(request: Request, claims=Depends(admin)):
        async def stream():
            while not await request.is_disconnected() and time.time() < claims["exp"]:
                payload = studio_state()
                yield "data: " + json.dumps(payload) + "\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get(prefix + "/channels", dependencies=[Depends(admin)])
    def channels():
        return core.channels()

    @app.post(prefix + "/cameras", dependencies=[Depends(admin)])
    def add_camera(body: CameraSettings):
        name, uri = core.source(body.channel_id)
        controller.add_camera(body.model_dump(), name, uri)
        return studio_state()

    @app.patch(prefix + "/cameras/{cid}", dependencies=[Depends(admin)])
    def patch_camera(cid: str, body: CameraPatch):
        controller.patch_camera(cid, body.model_dump(exclude_none=True))
        return studio_state()

    @app.delete(prefix + "/cameras/{cid}", dependencies=[Depends(admin)])
    def delete_camera(cid: str):
        controller.remove_camera(cid)
        return studio_state()

    @app.put(prefix + "/cameras/{cid}/hidden")
    def hide_camera(cid: str, body: Hidden, claims=Depends(admin)):
        controller.hide(cid, body.hidden)
        store.audit(claims["sub"], "camera-hidden", f"{cid}:{body.hidden}")
        return studio_state()

    @app.patch(prefix + "/program", dependencies=[Depends(admin)])
    def program(body: ProgramPatch):
        controller.set_program(body.model_dump(exclude_none=True))
        return studio_state()

    @app.post(prefix + "/program/switch", dependencies=[Depends(admin)])
    def switch(body: Switch):
        controller.switch(body.camera)
        return studio_state()

    @app.post(prefix + "/program/channel", dependencies=[Depends(admin)])
    def provision():
        return core.provision()

    @app.put(prefix + "/rotation", dependencies=[Depends(admin)])
    def rotation(body: Rotation):
        controller.rotation(body.model_dump())
        return studio_state()

    @app.put(prefix + "/scenes", dependencies=[Depends(admin)])
    def scene(body: Scene):
        controller.save_scene(body.model_dump())
        return studio_state()

    @app.delete(prefix + "/scenes/{alias}", dependencies=[Depends(admin)])
    def delete_scene(alias: str):
        with controller.lock:
            if alias not in controller.data["scenes"]:
                raise Rejected("Onbekende scène")
            del controller.data["scenes"][alias]
            controller.changed()
        return studio_state()

    @app.post(prefix + "/scenes/{alias}/apply", dependencies=[Depends(admin)])
    def apply_scene(alias: str):
        controller.apply_scene(alias)
        return studio_state()

    @app.put(prefix + "/chat", dependencies=[Depends(admin)])
    def chat_settings(body: ChatSettings):
        controller.chat_settings(body.model_dump())
        return studio_state()

    @app.post(prefix + "/chat/simulate", dependencies=[Depends(admin)])
    def simulate(body: ChatCommand):
        return controller.chat(body, preview=True)

    @app.get(prefix + "/chat/audit", dependencies=[Depends(admin)])
    def audit():
        return store.history()

    @app.get(prefix + "/bot/config", dependencies=[Depends(bot)])
    def bot_config():
        with controller.lock:
            return dict(controller.data["chat"])

    @app.post(prefix + "/bot/command", dependencies=[Depends(bot)])
    def bot_command(body: ChatCommand):
        if body.platform == "simulator":
            raise HTTPException(403, "Gebruik de beheerde simulator")
        return controller.chat(body)

    @app.post(prefix + "/bot/status", dependencies=[Depends(bot)])
    def bot_status(body: BotStatus):
        with controller.lock:
            # Adapter supplies fixed status codes, never provider error messages/tokens.
            controller.bots[body.platform] = {"state": body.state, "detail": body.detail, "at": time.time()}
        return {"ok": True}

    if settings.allow_test:
        @app.post(prefix + "/demo", dependencies=[Depends(admin)])
        def demo():
            if any(not cid.startswith("00000000-0000-0000-0000-") for cid in controller.data["cameras"]):
                raise Rejected("Gebruik de demo alleen op een afzonderlijke lege proefinstallatie")
            for i in range(13):
                cid = f"00000000-0000-0000-0000-{i:012d}"
                controller.add_camera({"channel_id": cid, "alias": f"demo-{i + 1}", "chat_enabled": True}, f"Demo {i + 1}", f"test://{i}")
            return studio_state()

    return app
