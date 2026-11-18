from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
LocalPath = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
ToolPath = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4096)]


class DraftProfile(Model):
    duration_seconds: int = Field(default=60, ge=10, le=900, strict=True)
    language: Literal["en", "hi", "bn"] = "en"
    style: Literal["storybook", "cel", "moonlit"] = "storybook"
    resolution: Literal["540p", "720p", "1080p"] = "720p"
    fps: Literal[15, 18, 24] = 24
    animation: Literal["subtle", "balanced", "expressive"] = "balanced"


class Draft(Model):
    title: Title
    story: str = Field(default="", max_length=100_000)
    profile: DraftProfile = Field(default_factory=DraftProfile)


PlanStage = Literal["not_started", "draft", "approved", "stale"]


class ProjectSummary(Model):
    id: str
    title: str
    profile: DraftProfile
    excerpt: str
    created_at: str
    updated_at: str
    archived_at: str | None = None
    plan_status: PlanStage = "not_started"


class Project(ProjectSummary):
    story: str
    folder: str
    folder_exists: bool


class ArchiveState(Model):
    archived: bool


class Settings(Model):
    projects_dir: LocalPath
    models_dir: LocalPath
    outputs_dir: LocalPath
    logs_dir: LocalPath
    ffmpeg_path: ToolPath = ""
    ffprobe_path: ToolPath = ""


class SettingsView(Model):
    values: Settings
    defaults: Settings
    data_dir: str
    editable: bool
