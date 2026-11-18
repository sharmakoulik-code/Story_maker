from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .schemas import DraftProfile, Model, ProjectSummary, Title

MAX_SCENES = 40
MAX_CHARACTERS = 24
MAX_PLACES = 20
MAX_PROPS = 24
MAX_DIALOGUE = 32
MIN_GENERATED_SCENE = 4
MAX_REVISION = 2**63 - 1

AssetId = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1800)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Tempo = Literal["cut", "dissolve", "fade_to_black", "slide", "zoom"]
Narration = Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)]
Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)]
Revision = Annotated[int, Field(ge=1, le=MAX_REVISION, strict=True)]


def source_digest(story: str, profile: DraftProfile) -> str:
    # The project name and storage location don't affect the production plan.
    body = json.dumps([story.replace("\r\n", "\n").replace("\r", "\n").strip(), profile.model_dump()],
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class StoryArc(Model):
    main_plot: Note = ""
    beginning: Note = ""
    conflict: Note = ""
    emotional_development: Note = ""
    climax: Note = ""
    ending: Note = ""


class Reference(Model):
    id: Key
    name: Title
    description: Note = ""


class CharacterDesign(Model):
    name: Title
    description: Note = ""
    appearance: Note = ""
    face: Short = ""
    body: Short = ""
    clothing: Short = ""
    hair: Short = ""
    eyes: Short = ""
    accessories: Short = ""
    generation_notes: Note = ""
    personality: Short = ""
    age_range: Short = ""


class LibraryPin(Model):
    character_id: AssetId
    image_id: AssetId | None = None


class Character(CharacterDesign):
    id: Key
    role: Literal["main", "supporting"] = "supporting"
    relationships: Note = ""
    library_pin: LibraryPin | None = None


class StoryBible(Model):
    setting: Note = ""
    visual_style: Note = ""
    continuity_rules: Note = ""
    characters: list[Character] = Field(default_factory=list, max_length=MAX_CHARACTERS)
    locations: list[Reference] = Field(default_factory=list, max_length=MAX_PLACES)
    props: list[Reference] = Field(default_factory=list, max_length=MAX_PROPS)


class Appearance(Model):
    character_id: Key
    emotion: Short = ""


class DialogueLine(Model):
    character_id: Key | None = None
    speaker: Short = ""
    text: Note = ""


class Scene(Model):
    id: Key
    title: Title
    duration_seconds: int = Field(ge=1, le=900, strict=True)
    narration: Narration = ""
    dialogue: list[DialogueLine] = Field(default_factory=list, max_length=MAX_DIALOGUE)
    cast: list[Appearance] = Field(default_factory=list, max_length=MAX_CHARACTERS)
    location_id: Key | None = None
    environment: Note = ""
    prop_ids: list[Key] = Field(default_factory=list, max_length=MAX_PROPS)
    visual_description: Note = ""
    image_prompt_override: Prompt = ""
    camera: Note = ""
    animation: Note = ""
    sound_effects: Note = ""
    transition: Tempo = "cut"


class PlanDocument(Model):
    analysis: StoryArc
    bible: StoryBible
    scenes: list[Scene] = Field(min_length=1, max_length=MAX_SCENES)

    @model_validator(mode="after")
    def check_references(self) -> PlanDocument:
        def keys(items, label):
            ids = {item.id for item in items}
            if len(ids) != len(items):
                raise ValueError(f"{label} must have unique IDs.")
            return ids

        characters = keys(self.bible.characters, "Characters")
        locations = keys(self.bible.locations, "Locations")
        props = keys(self.bible.props, "Props")
        keys(self.scenes, "Scenes")
        for index, scene in enumerate(self.scenes, 1):
            cast = {appearance.character_id for appearance in scene.cast}
            speakers = {line.character_id for line in scene.dialogue if line.character_id is not None}
            if not cast <= characters or not speakers <= characters or len(cast) != len(scene.cast):
                raise ValueError(f"Scene {index} has a missing or repeated character reference.")
            if scene.location_id is not None and scene.location_id not in locations:
                raise ValueError(f"Scene {index} has a missing location reference.")
            if not set(scene.prop_ids) <= props or len(set(scene.prop_ids)) != len(scene.prop_ids):
                raise ValueError(f"Scene {index} has a missing or repeated prop reference.")
        return self


class PlanSource(Model):
    engine: Literal["local-rules-v1"] = "local-rules-v1"
    script_hint: Literal["Latin", "Devanagari", "Bengali", "mixed", "unknown"]
    story_words: int
    source_beats: int
    spoken_beats: int
    excerpts: dict[Key, Note]


class SceneTiming(Model):
    scene_id: Key
    number: int
    start_seconds: int
    end_seconds: int
    spoken_words: int
    speech_seconds: float
    minimum_seconds: int
    fits: bool
    image_prompt: str


class PlanTiming(Model):
    target_seconds: int
    planned_seconds: int
    words_per_minute: int
    spoken_words: int
    scenes: list[SceneTiming]
    issues: list[str]
    cautions: list[str]
    can_approve: bool


class SavedPlan(Model):
    revision: int
    status: Literal["draft", "approved", "stale"]
    created_at: str
    updated_at: str
    approved_at: str | None
    profile: DraftProfile
    document: PlanDocument
    source: PlanSource
    timing: PlanTiming


class PlanView(Model):
    project: ProjectSummary
    has_story: bool
    can_adopt_target: bool
    plan: SavedPlan | None


class GeneratePlan(Model):
    expected_revision: Revision | None = None


class SavePlan(Model):
    revision: Revision
    document: PlanDocument
    fit_duration: bool = False


class PlanApproval(Model):
    revision: Revision
    approved: bool


class AdoptTarget(Model):
    revision: Revision


class VersionSummary(Model):
    revision: int
    saved_at: str
    approved_at: str | None
    can_restore: bool


class PlanHistory(Model):
    versions: list[VersionSummary]
    next_before: int | None


class PlanVersion(Model):
    revision: int
    saved_at: str
    approved_at: str | None
    profile: DraftProfile
    document: PlanDocument
    source: PlanSource


class RestoreVersion(Model):
    revision: Revision
    version: Revision
