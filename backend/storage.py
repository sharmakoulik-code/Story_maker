from __future__ import annotations

import os
import sqlite3
from contextlib import closing, contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .motion.schema import SCHEMA as MOTION_SCHEMA
from .plan_models import source_digest
from .schemas import Draft, DraftProfile, Project, ProjectSummary, Settings
from .visual_schema import VISUAL_SCHEMA


SCHEMA_VERSION = 5

PLAN_SUMMARY = """CASE WHEN plan.project_id IS NULL THEN 'not_started'
                         WHEN plan.stale = 1 THEN 'stale'
                         WHEN plan.approved_at IS NOT NULL THEN 'approved'
                         ELSE 'draft' END AS plan_status"""
PLAN_JOIN = "FROM projects AS p LEFT JOIN story_plans AS plan ON p.id = plan.project_id"


class WorkspaceError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def local_path(value: Path | str) -> Path:
    """Use local absolute paths only; never pass a UNC path to a filesystem probe."""
    def check(path: Path) -> None:
        if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
            raise ValueError("Use an absolute local path, not a network share.")
        if os.name == "nt":
            import ctypes

            # 4 = DRIVE_REMOTE (mapped network drive). UNC is rejected above.
            if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) == 4:
                raise ValueError("Mapped network drives are not supported.")

    path = Path(value).expanduser()
    check(path)
    path = path.resolve()
    check(path)
    return path


def default_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return root / "AnimeStudio"
    root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "anime-studio"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def excerpt(story: str) -> str:
    return " ".join(story.split())[:180]


class Workspace:
    def __init__(self, base: Path) -> None:
        self.base = local_path(base)
        self.database = self.base / "database" / "studio.sqlite3"
        self.defaults = Settings(
            projects_dir=str(self.base / "projects"),
            models_dir=str(self.base / "models"),
            outputs_dir=str(self.base / "outputs"),
            logs_dir=str(self.base / "logs"),
        )

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.database, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection

    def initialize(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError("This workspace was opened by a newer version of Koma Studio. Upgrade Koma Studio or choose another data folder.")
            if version == 0:
                db.execute("""
                    CREATE TABLE projects (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        story TEXT NOT NULL,
                        profile TEXT NOT NULL,
                        folder TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        archived_at TEXT
                    )
                """)
                db.execute("CREATE INDEX projects_recent ON projects (updated_at DESC, id)")
                db.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL)")
            if version < 2:
                db.execute("""
                    CREATE TABLE story_plans (
                        project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                        source_digest TEXT NOT NULL,
                        profile TEXT NOT NULL,
                        document TEXT NOT NULL,
                        source TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        stale INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0, 1)),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        approved_at TEXT
                    )
                """)
            if version < 3:
                db.execute("""
                    CREATE TABLE story_plan_versions (
                        project_id TEXT NOT NULL REFERENCES story_plans(project_id) ON DELETE CASCADE,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        source_digest TEXT NOT NULL,
                        profile TEXT NOT NULL,
                        document TEXT NOT NULL,
                        source TEXT NOT NULL,
                        saved_at TEXT NOT NULL,
                        approved_at TEXT,
                        PRIMARY KEY (project_id, revision)
                    )
                """)
                db.execute("""
                    INSERT INTO story_plan_versions (project_id, revision, source_digest, profile, document, source, saved_at, approved_at)
                    SELECT project_id, revision, source_digest, profile, document, source, updated_at, approved_at
                    FROM story_plans WHERE approved_at IS NOT NULL
                """)
            if version < 4:
                for statement in VISUAL_SCHEMA:
                    db.execute(statement)
            if version < 5:
                for statement in MOTION_SCHEMA:
                    db.execute(statement)
            if version < SCHEMA_VERSION:
                db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        for field in ("projects_dir", "models_dir", "outputs_dir", "logs_dir"):
            Path(getattr(self.defaults, field)).mkdir(parents=True, exist_ok=True)

    def get_settings(self) -> Settings:
        with self.connect() as db:
            row = db.execute("SELECT data FROM settings WHERE id = 1").fetchone()
        return Settings.model_validate_json(row["data"]) if row else self.defaults

    def save_settings(self, settings: Settings) -> Settings:
        normalized: dict[str, str] = {}
        for field in ("projects_dir", "models_dir", "outputs_dir", "logs_dir", "ffmpeg_path", "ffprobe_path"):
            value = getattr(settings, field)
            if not value:
                normalized[field] = ""
                continue
            name = field.removesuffix("_dir").removesuffix("_path")
            try:
                path = local_path(value)
                if field.endswith("_path"):
                    if path.name.lower() not in (name, f"{name}.exe") or not path.is_file():
                        raise ValueError(f"Choose an existing {name} executable.")
                elif path == self.database.parent or self.database.parent in path.parents:
                    raise ValueError("Choose a folder outside the database directory.")
                normalized[field] = str(path)
            except (OSError, ValueError, RuntimeError) as error:
                raise WorkspaceError(422, f"{name.capitalize()}: {error}") from error
        for field in ("projects_dir", "models_dir", "outputs_dir", "logs_dir"):
            try:
                Path(normalized[field]).mkdir(parents=True, exist_ok=True)
            except OSError as error:
                name = field.removesuffix("_dir").capitalize()
                raise WorkspaceError(422, f"{name}: could not open or create this folder. Check the path and permissions.") from error
        result = Settings.model_validate(normalized)
        with self.connect() as db:
            db.execute("INSERT INTO settings (id, data) VALUES (1, ?) ON CONFLICT (id) DO UPDATE SET data = excluded.data",
                       (result.model_dump_json(),))
        return result

    def summarize(self, row: sqlite3.Row) -> ProjectSummary:
        return ProjectSummary(
            id=row["id"], title=row["title"], profile=DraftProfile.model_validate_json(row["profile"]),
            excerpt=excerpt(row["story"]), created_at=row["created_at"],
            updated_at=row["updated_at"], archived_at=row["archived_at"], plan_status=row["plan_status"],
        )

    def _project(self, row: sqlite3.Row) -> Project:
        try:
            exists = Path(row["folder"]).is_dir()
        except OSError:
            exists = False
        return Project(**self.summarize(row).model_dump(), story=row["story"], folder=row["folder"], folder_exists=exists)

    def list_projects(self) -> list[ProjectSummary]:
        with self.connect() as db:
            rows = db.execute(f"""
                SELECT p.id, p.title, p.profile, substr(p.story, 1, 512) AS story, p.created_at, p.updated_at,
                       p.archived_at, {PLAN_SUMMARY}
                {PLAN_JOIN} ORDER BY p.updated_at DESC, p.id
            """).fetchall()
        return [self.summarize(row) for row in rows]

    def find_project(self, db: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = db.execute(f"SELECT p.*, {PLAN_SUMMARY} {PLAN_JOIN} WHERE p.id = ?", (project_id,)).fetchone()
        if row is None:
            raise WorkspaceError(404, "This project is not in the local library.")
        return row

    def get_project(self, project_id: str) -> Project:
        with self.connect() as db:
            return self._project(self.find_project(db, project_id))

    def create_project(self, draft: Draft) -> Project:
        project_id = uuid4().hex
        try:
            folder = local_path(self.get_settings().projects_dir) / project_id
            folder.mkdir(parents=True, exist_ok=False)
        except (OSError, ValueError, RuntimeError) as error:
            raise WorkspaceError(422, "Could not create the project folder. Check the Projects folder in System & models.") from error
        now = timestamp()
        try:
            with self.connect() as db:
                db.execute("""
                    INSERT INTO projects (id, title, story, profile, folder, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (project_id, draft.title, draft.story, draft.profile.model_dump_json(), str(folder), now, now))
                project = self._project(self.find_project(db, project_id))
        except Exception:
            with suppress(OSError):
                folder.rmdir()  # Never remove files if anything has used this directory.
            raise
        return project

    def update_project(self, project_id: str, draft: Draft) -> Project:
        now = timestamp()
        digest = source_digest(draft.story, draft.profile)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = self.find_project(db, project_id)
            cursor = db.execute("""
                UPDATE projects SET title = ?, story = ?, profile = ?, updated_at = ?
                WHERE id = ? AND archived_at IS NULL
            """, (draft.title, draft.story, draft.profile.model_dump_json(), now, project_id))
            if cursor.rowcount == 0:
                raise WorkspaceError(409, "Restore this archived project before editing it.")
            previous_digest = source_digest(previous["story"], DraftProfile.model_validate_json(previous["profile"]))
            if previous_digest != digest:
                db.execute("""
                    UPDATE story_plans SET stale = (source_digest <> ?), approved_at = NULL,
                        revision = revision + 1, updated_at = ? WHERE project_id = ?
                """, (digest, now, project_id))
            return self._project(self.find_project(db, project_id))

    def set_archived(self, project_id: str, archived: bool) -> Project:
        now = timestamp()
        with self.connect() as db:
            if archived:
                db.execute("UPDATE projects SET archived_at = ?, updated_at = ? WHERE id = ? AND archived_at IS NULL",
                           (now, now, project_id))
            else:
                db.execute("UPDATE projects SET archived_at = NULL, updated_at = ? WHERE id = ? AND archived_at IS NOT NULL",
                           (now, project_id))
            return self._project(self.find_project(db, project_id))
