"""Timeline contract. Coordinates are on a 540 × 960 stage; artwork is sampled at 2× for export."""
from __future__ import annotations

from math import ceil
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

WIDTH, HEIGHT, FPS = 540, 960, 30
MAX_FRAMES = 60 * FPS
MAX_LAYERS = 40
MAX_KEYS = 96
MAX_ASSETS = 72
MAX_SHOT_PIXELS = 12_000_000
Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")]
Id = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Position = Annotated[float, Field(ge=-4096, le=4096)]
Scale = Annotated[float, Field(ge=0.05, le=4)]
Ease = Literal["smooth", "linear", "hold"]
EncoderMode = Literal["auto", "software"]
JobState = Literal["queued", "rendering", "cancelling", "cancelled", "failed", "complete"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Pose(Model):
    x: Position = 0
    y: Position = 0
    scale_x: Scale = 1
    scale_y: Scale = 1
    rotation: float = Field(0, ge=-720, le=720)
    opacity: float = Field(1, ge=0, le=1)
    visible: bool = True


class PoseKey(Pose):
    frame: int = Field(ge=0, lt=900)
    ease: Ease = "smooth"


class CameraPose(Model):
    x: Position = WIDTH / 2
    y: Position = HEIGHT / 2
    zoom: float = Field(1, ge=0.5, le=4)


class CameraKey(CameraPose):
    frame: int = Field(ge=0, lt=900)
    ease: Ease = "smooth"


class Camera(Model):
    mode: Literal["locked", "keyframed", "tracking"] = "locked"
    target: Key | None = None
    pose: CameraPose = Field(default_factory=CameraPose)
    keys: list[CameraKey] = Field(default_factory=list, max_length=MAX_KEYS)


class Layer(Model):
    id: Key
    name: Name
    asset: Key | None = None
    parent: Key | None = None
    pivot_x: Position = 0
    pivot_y: Position = 0
    pose: Pose = Field(default_factory=Pose)
    keys: list[PoseKey] = Field(default_factory=list, max_length=MAX_KEYS)


class Shot(Model):
    id: Key
    name: Name
    frames: int = Field(90, ge=15, le=900)
    speed: Literal[0.5, 0.75, 1.0, 1.25, 1.5, 2.0] = 1.0
    camera: Camera = Field(default_factory=Camera)
    layers: list[Layer] = Field(default_factory=list, max_length=MAX_LAYERS)

    @property
    def output_frames(self) -> int:
        return ceil(self.frames / self.speed)

    @model_validator(mode="after")
    def check_tracks(self) -> Shot:
        layers = {layer.id: layer for layer in self.layers}
        if len(layers) != len(self.layers):
            raise ValueError("Layer IDs must be unique within a shot.")
        for layer in self.layers:
            seen = {layer.id}
            parent = layer.parent
            while parent is not None:
                if parent not in layers or parent in seen or len(seen) >= 8:
                    raise ValueError("Layer parents must be in the same shot, with no cycles and at most eight levels.")
                seen.add(parent)
                parent = layers[parent].parent
        if self.camera.mode == "tracking" and self.camera.target not in layers:
            raise ValueError("Select a layer for this camera to track.")
        for keys in [self.camera.keys, *(layer.keys for layer in self.layers)]:
            indices = [key.frame for key in keys]
            if indices != sorted(set(indices)) or (indices and indices[-1] >= self.frames):
                raise ValueError("Keyframes must be unique, ordered, and inside the shot duration.")
        return self


class Sequence(Model):
    title: Name
    shots: list[Shot] = Field(min_length=1, max_length=12)

    @property
    def output_frames(self) -> int:
        return sum(shot.output_frames for shot in self.shots)

    @model_validator(mode="after")
    def check_sequence(self) -> Sequence:
        if len({shot.id for shot in self.shots}) != len(self.shots):
            raise ValueError("Shot IDs must be unique within a sequence.")
        if self.output_frames > MAX_FRAMES:
            raise ValueError("This version supports up to 60 seconds per animation after speed changes.")
        if sum(len(shot.camera.keys) + sum(len(layer.keys) for layer in shot.layers) for shot in self.shots) > 2400:
            raise ValueError("This sequence exceeds the 2,400 keyframe limit.")
        return self


class SequenceSummary(Model):
    id: Id
    revision: int
    title: Name
    sample: bool
    frames: int
    shots: int
    updated_at: str


class Asset(Model):
    id: Key
    name: str
    width: int
    height: int
    url: str


class SequenceView(SequenceSummary):
    document: Sequence
    assets: list[Asset]


class NewSequence(Model):
    title: Name


class SaveSequence(Model):
    revision: int = Field(ge=1, le=2_000_000_000)
    document: Sequence


class ExportRequest(Model):
    revision: int = Field(ge=1, le=2_000_000_000)
    mode: EncoderMode = "auto"


class ExportJob(Model):
    id: Id
    sequence_id: Id
    revision: int
    state: JobState
    done: int
    frames: int
    encoder: str | None
    message: str
    filename: str
    created_at: str
    updated_at: str
    output_path: str | None = None
