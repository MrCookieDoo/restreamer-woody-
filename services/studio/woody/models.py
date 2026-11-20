"""Validated public interfaces. Source URLs never cross the Studio API."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Alias = str


class CameraSettings(Model):
    channel_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    alias: str = Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")
    chat_enabled: bool = False


class SlateUpload(Model):
    image_data: str = Field(min_length=1, max_length=5_600_000)


class CameraPatch(Model):
    alias: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,31}$")
    chat_enabled: bool | None = None


class Scene(Model):
    alias: str = Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")
    name: str = Field(min_length=1, max_length=80)
    layout: Literal["six", "full", "safe"] = "six"
    cameras: list[str | None] = Field(default_factory=list, max_length=6)
    chat_enabled: bool = False


class Rotation(Model):
    enabled: bool = True
    interval_seconds: int = Field(default=180, ge=10, le=86400)
    order: list[str] = Field(default_factory=list, max_length=13)


class ProgramPatch(Model):
    safe: bool | None = None
    pinned: bool | None = None
    layout: Literal["six", "full"] | None = None
    border_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    border_width: int | None = Field(default=None, ge=0, le=12)


class Switch(Model):
    camera: str


class Hidden(Model):
    hidden: bool


class ChatSettings(Model):
    enabled: bool = False
    dry_run: bool = True
    viewer_enabled: Literal[False] = False
    global_cooldown: int = Field(default=10, ge=1, le=3600)
    user_cooldown: int = Field(default=30, ge=1, le=3600)
    twitch_channel: str = Field(default="", pattern=r"^[a-z0-9_]{0,25}$")
    youtube_channel: str = Field(default="", max_length=80)


class ChatCommand(Model):
    platform: Literal["twitch", "youtube", "simulator"]
    message_id: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    role: Literal["viewer", "moderator", "owner"]
    text: str = Field(min_length=1, max_length=200)
    timestamp: float = Field(allow_inf_nan=False)
    simulate: bool = False


class BotStatus(Model):
    platform: Literal["twitch", "youtube"]
    state: Literal["disabled", "waiting", "connected", "error"]
    detail: str = Field(default="", max_length=120)
