from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .plan_models import AssetId, CharacterDesign, Key, PlanView, Revision
from .schemas import Model

ShotRevision = Annotated[int, Field(ge=0, le=2**63 - 1, strict=True)]
Credit = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class Credits(Model):
    source: Credit = ""
    license_note: Credit = ""


class StillVersion(Model):
    id: AssetId
    number: int
    original_name: str
    source: str
    license_note: str
    width: int
    height: int
    bytes: int
    created_at: str
    last_approved_at: str | None
    available: bool


class StillHistory(Model):
    versions: list[StillVersion]
    next_before: int | None


class LibraryCharacter(Model):
    id: AssetId
    revision: Revision
    design: CharacterDesign
    reference: StillVersion | None
    reference_count: int
    created_at: str
    updated_at: str
    archived_at: str | None


class CharacterEdit(Model):
    revision: Revision
    design: CharacterDesign


class CharacterArchive(Model):
    revision: Revision
    archived: bool


class ChooseReference(Model):
    revision: Revision
    image_id: AssetId


class BoardShot(Model):
    scene_id: Key
    title: str
    revision: ShotRevision = 0
    active: StillVersion | None = None
    version_count: int = 0
    status: Literal["empty", "review", "approved", "changed", "missing"] = "empty"


class StoryboardView(Model):
    plan: PlanView
    shots: list[BoardShot]
    off_board: list[BoardShot]
    off_board_count: int


class ChooseFrame(Model):
    plan_revision: Revision
    shot_revision: ShotRevision
    image_id: AssetId


class ReviewTarget(Model):
    scene_id: Key
    revision: ShotRevision


class ShotReview(Model):
    plan_revision: Revision
    targets: list[ReviewTarget] = Field(min_length=1, max_length=40)
    approved: bool

    @model_validator(mode="after")
    def unique_shots(self):
        if len({entry.scene_id for entry in self.targets}) != len(self.targets):
            raise ValueError("A shot can only be selected once.")
        return self
