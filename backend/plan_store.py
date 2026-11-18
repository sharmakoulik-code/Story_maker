"""SQLite plan lifecycle and optimistic concurrency for the local review workflow."""
from __future__ import annotations

import sqlite3
from uuid import uuid4

from .plan_models import (PlanDocument, PlanHistory, PlanSource, PlanVersion, PlanView,
                          SavedPlan, SavePlan, VersionSummary, source_digest)
from .plan_timing import fit_durations, timing_for
from .planner import build_plan
from .schemas import DraftProfile
from .storage import Workspace, WorkspaceError, timestamp


class PlanStore:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    @staticmethod
    def row(db: sqlite3.Connection, project_id: str) -> sqlite3.Row | None:
        return db.execute("SELECT * FROM story_plans WHERE project_id = ?", (project_id,)).fetchone()

    @staticmethod
    def writable(project: sqlite3.Row) -> None:
        if project["archived_at"]:
            raise WorkspaceError(409, "Restore this archived project before changing its plan.")

    @staticmethod
    def check_revision(row: sqlite3.Row | None, expected: int | None) -> None:
        if expected != (row["revision"] if row else None):
            raise WorkspaceError(409, "The saved plan changed. Reopen it before generating, saving or approving again.")

    @staticmethod
    def check_current(row: sqlite3.Row | None) -> sqlite3.Row:
        if row is None:
            raise WorkspaceError(409, "Generate a story plan first.")
        if row["stale"]:
            raise WorkspaceError(409, "The story or production preferences changed. Generate a new plan from the saved draft first.")
        return row

    def view(self, project_id: str) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project = self.workspace.find_project(db, project_id)
            row = self.row(db, project_id)
        return self._view(project, row)

    def _view(self, project: sqlite3.Row, row: sqlite3.Row | None) -> PlanView:
        plan = None
        can_adopt_target = False
        if row:
            document = PlanDocument.model_validate_json(row["document"])
            profile = DraftProfile.model_validate_json(row["profile"])
            plan = SavedPlan(revision=row["revision"], status=project["plan_status"], created_at=row["created_at"],
                             updated_at=row["updated_at"], approved_at=row["approved_at"], profile=profile, document=document,
                             source=PlanSource.model_validate_json(row["source"]), timing=timing_for(document, profile))
            can_adopt_target = bool(not project["archived_at"] and self.target_only_change(project, row))
        return PlanView(project=self.workspace.summarize(project), has_story=any(char.isalnum() for char in project["story"]),
                        can_adopt_target=can_adopt_target, plan=plan)

    @staticmethod
    def target_only_change(project: sqlite3.Row, row: sqlite3.Row) -> bool:
        if not row["stale"]:
            return False
        before = DraftProfile.model_validate_json(row["profile"])
        current = DraftProfile.model_validate_json(project["profile"])
        return (before.duration_seconds != current.duration_seconds
                and before.model_dump(exclude={"duration_seconds"}) == current.model_dump(exclude={"duration_seconds"})
                and source_digest(project["story"], before) == row["source_digest"])

    @staticmethod
    def touch(db: sqlite3.Connection, project_id: str, now: str) -> None:
        db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))

    @staticmethod
    def snapshot(db: sqlite3.Connection, project_id: str) -> None:
        # Keep the exact saved revision before replacement. Snapshot and update commit together.
        db.execute("""
            INSERT INTO story_plan_versions (project_id, revision, source_digest, profile, document, source, saved_at, approved_at)
            SELECT project_id, revision, source_digest, profile, document, source, updated_at, approved_at
            FROM story_plans WHERE project_id = ?
            ON CONFLICT (project_id, revision) DO NOTHING
        """, (project_id,))

    def generate(self, project_id: str, expected: int | None) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project = self.workspace.find_project(db, project_id)
            self.writable(project)
            self.check_revision(self.row(db, project_id), expected)
        profile = DraftProfile.model_validate_json(project["profile"])
        digest = source_digest(project["story"], profile)
        # No write lock while doing CPU work. Validate both the revision and the input again before committing.
        try:
            document, source = build_plan(project["story"], profile)
        except ValueError as error:
            raise WorkspaceError(422, "Could not create a plan. Add some story text with words and try again.") from error
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self.workspace.find_project(db, project_id)
            self.writable(current)
            self.check_revision(self.row(db, project_id), expected)
            if digest != source_digest(current["story"], DraftProfile.model_validate_json(current["profile"])):
                raise WorkspaceError(409, "The story changed while planning. Reopen the saved draft and try again.")
            now = timestamp()
            if expected is not None:
                self.snapshot(db, project_id)
                # New scenes are not revisions of the old storyboard shots. Keep the old IDs in history.
                replacements = {scene.id: f"scene-{uuid4().hex}" for scene in document.scenes}
                document = document.model_copy(update={"scenes": [scene.model_copy(update={"id": replacements[scene.id]})
                                                                 for scene in document.scenes]})
                source = source.model_copy(update={"excerpts": {replacements[key]: text for key, text in source.excerpts.items()}})
            db.execute("""
                INSERT INTO story_plans (project_id, source_digest, profile, document, source, revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (project_id) DO UPDATE SET source_digest = excluded.source_digest, profile = excluded.profile,
                    document = excluded.document, source = excluded.source, revision = excluded.revision,
                    updated_at = excluded.updated_at, stale = 0, approved_at = NULL
            """, (project_id, digest, profile.model_dump_json(), document.model_dump_json(), source.model_dump_json(),
                  (expected or 0) + 1, now, now))
            self.touch(db, project_id, now)
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
        return self._view(project, row)

    @staticmethod
    def validate_pins(db: sqlite3.Connection, document: PlanDocument) -> None:
        for character in document.bible.characters:
            pin = character.library_pin
            if pin is None:
                continue
            entry = db.execute("SELECT id FROM cast_library WHERE id = ?", (pin.character_id,)).fetchone()
            if entry is None or (pin.image_id is not None and not db.execute(
                "SELECT id FROM studio_images WHERE id = ? AND character_id = ?", (pin.image_id, pin.character_id)
            ).fetchone()):
                raise WorkspaceError(422, "A pinned character reference is not in this library. Choose the design again.")

    def save(self, project_id: str, request: SavePlan) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
            self.writable(project)
            self.check_revision(row, request.revision)
            row = self.check_current(row)
            document = request.document
            if request.fit_duration:
                try:
                    document = fit_durations(document, DraftProfile.model_validate_json(row["profile"]))
                except ValueError as error:
                    raise WorkspaceError(422, str(error)) from error
            previous = PlanDocument.model_validate_json(row["document"])
            if document != previous:
                self.validate_pins(db, document)
                scene_ids = {scene.id for scene in document.scenes}
                if any(scene.id not in scene_ids for scene in previous.scenes):
                    self.snapshot(db, project_id)
                now = timestamp()
                serialized = document.model_dump_json()
                db.execute("UPDATE story_plans SET document = ?, revision = revision + 1, updated_at = ?, approved_at = NULL WHERE project_id = ?",
                           (serialized, now, project_id))
                titles = {scene.id: scene.title for scene in previous.scenes}
                for scene in document.scenes:
                    if scene.id in titles and titles[scene.id] != scene.title:
                        db.execute("UPDATE board_shots SET title = ? WHERE project_id = ? AND scene_id = ?",
                                   (scene.title, project_id, scene.id))
                self.touch(db, project_id, now)
                project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
        return self._view(project, row)

    def approve(self, project_id: str, revision: int, approved: bool) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
            self.writable(project)
            self.check_revision(row, revision)
            row = self.check_current(row)
            if approved:
                timing = timing_for(PlanDocument.model_validate_json(row["document"]), DraftProfile.model_validate_json(row["profile"]))
                if not timing.can_approve:
                    raise WorkspaceError(422, "Resolve the timing issues before approving. " + timing.issues[0])
            if approved != bool(row["approved_at"]):
                now = timestamp()
                db.execute("UPDATE story_plans SET approved_at = ?, updated_at = ?, revision = revision + 1 WHERE project_id = ?",
                           (now if approved else None, now, project_id))
                if approved:
                    self.snapshot(db, project_id)
                self.touch(db, project_id, now)
                project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
        return self._view(project, row)

    def adopt_target(self, project_id: str, revision: int) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
            self.writable(project)
            self.check_revision(row, revision)
            if row is None or not self.target_only_change(project, row):
                raise WorkspaceError(409, "Only a duration change can be applied to the existing plan without replanning.")
            profile = DraftProfile.model_validate_json(project["profile"])
            now = timestamp()
            db.execute("""
                UPDATE story_plans SET profile = ?, source_digest = ?, stale = 0, approved_at = NULL,
                    revision = revision + 1, updated_at = ? WHERE project_id = ?
            """, (profile.model_dump_json(), source_digest(project["story"], profile), now, project_id))
            self.touch(db, project_id, now)
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
        return self._view(project, row)

    def history(self, project_id: str, before: int | None) -> PlanHistory:
        page_size = 12
        clause = " AND revision < ?" if before is not None else ""
        parameters = (project_id, before, page_size + 1) if before is not None else (project_id, page_size + 1)
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project = self.workspace.find_project(db, project_id)
            rows = db.execute("""
                SELECT revision, source_digest, saved_at, approved_at FROM story_plan_versions
                WHERE project_id = ?""" + clause + " ORDER BY revision DESC LIMIT ?", parameters).fetchall()
        digest = source_digest(project["story"], DraftProfile.model_validate_json(project["profile"]))
        return PlanHistory(versions=[VersionSummary(revision=row["revision"], saved_at=row["saved_at"], approved_at=row["approved_at"],
                           can_restore=(not project["archived_at"] and row["source_digest"] == digest)) for row in rows[:page_size]],
                           next_before=rows[page_size - 1]["revision"] if len(rows) > page_size else None)

    @staticmethod
    def version_row(db: sqlite3.Connection, project_id: str, revision: int) -> sqlite3.Row:
        row = db.execute("SELECT * FROM story_plan_versions WHERE project_id = ? AND revision = ?", (project_id, revision)).fetchone()
        if row is None:
            raise WorkspaceError(404, "That saved plan version was not found in this project.")
        return row

    def version(self, project_id: str, revision: int) -> PlanVersion:
        with self.workspace.connect() as db:
            row = self.version_row(db, project_id, revision)
        return PlanVersion(revision=row["revision"], saved_at=row["saved_at"], approved_at=row["approved_at"],
                           profile=DraftProfile.model_validate_json(row["profile"]), document=PlanDocument.model_validate_json(row["document"]),
                           source=PlanSource.model_validate_json(row["source"]))

    def restore(self, project_id: str, revision: int, version: int) -> PlanView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
            self.writable(project)
            self.check_revision(row, revision)
            previous = self.version_row(db, project_id, version)
            digest = source_digest(project["story"], DraftProfile.model_validate_json(project["profile"]))
            if previous["source_digest"] != digest:
                raise WorkspaceError(409, "That version uses a different story or profile. Download it for reference, or restore the matching story and preferences first.")
            self.snapshot(db, project_id)
            now = timestamp()
            db.execute("""
                UPDATE story_plans SET source_digest = ?, profile = ?, document = ?, source = ?, stale = 0,
                    approved_at = NULL, revision = revision + 1, updated_at = ? WHERE project_id = ?
            """, (digest, previous["profile"], previous["document"], previous["source"], now, project_id))
            self.touch(db, project_id, now)
            project, row = self.workspace.find_project(db, project_id), self.row(db, project_id)
        return self._view(project, row)
