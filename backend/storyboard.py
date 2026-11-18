"""Per-scene still versions and review. Story-plan IDs define shot identity, not scene order."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import BinaryIO

from .images import ImageStore
from .plan_models import PlanDocument, Scene
from .plan_store import PlanStore
from .storage import Workspace, WorkspaceError, timestamp
from .visual_models import BoardShot, ChooseFrame, Credits, ShotReview, StillHistory, StoryboardView


def visual_context(document: PlanDocument, scene: Scene) -> str:
    bible = document.bible
    cast = {entry.character_id for entry in scene.cast}
    visual = {
        "scene": scene.model_dump(exclude={"title", "duration_seconds", "narration", "dialogue", "transition", "animation", "sound_effects"}),
        "style": bible.visual_style, "setting": bible.setting, "continuity": bible.continuity_rules,
        "characters": [person.model_dump(exclude={"role", "personality", "relationships"}) for person in bible.characters if person.id in cast],
        "location": next((item.model_dump() for item in bible.locations if item.id == scene.location_id), None),
        "props": [item.model_dump() for item in bible.props if item.id in scene.prop_ids],
    }
    data = json.dumps(visual, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class StoryboardStore:
    def __init__(self, workspace: Workspace, plans: PlanStore, images: ImageStore):
        self.workspace = workspace
        self.plans = plans
        self.images = images

    @staticmethod
    def current_shot(db, project_id: str, scene_id: str):
        return db.execute("SELECT * FROM board_shots WHERE project_id = ? AND scene_id = ?", (project_id, scene_id)).fetchone()

    @staticmethod
    def check_shot(row, expected: int):
        if expected != (row["revision"] if row is not None else 0):
            raise WorkspaceError(409, "This shot changed in another view. Reopen the storyboard and try again.")

    def check_plan(self, db, project_id: str, revision: int):
        project = self.workspace.find_project(db, project_id)
        self.plans.writable(project)
        plan = self.plans.row(db, project_id)
        self.plans.check_revision(plan, revision)
        current = self.plans.check_current(plan)
        return project, current, PlanDocument.model_validate_json(current["document"])

    @staticmethod
    def scene_in(document: PlanDocument, scene_id: str) -> Scene:
        scene = next((entry for entry in document.scenes if entry.id == scene_id), None)
        if scene is None:
            raise WorkspaceError(409, "That scene is no longer on the saved storyboard. Its images are kept off the board.")
        return scene

    @staticmethod
    def check_owner(db, project_id: str, scene_id: str, image_id: str):
        return db.execute("SELECT * FROM studio_images WHERE id = ? AND project_id = ? AND scene_id = ?",
                          (image_id, project_id, scene_id)).fetchone()

    def view(self, project_id: str) -> StoryboardView:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project = self.workspace.find_project(db, project_id)
            plan = self.plans.row(db, project_id)
            rows = db.execute("""
                SELECT i.*, s.title, s.revision, s.approved_at, s.approved_context,
                    (SELECT count(*) FROM studio_images AS v WHERE v.project_id = s.project_id AND v.scene_id = s.scene_id) AS version_count
                FROM board_shots AS s JOIN studio_images AS i ON i.id = s.active_image
                WHERE s.project_id = ? ORDER BY i.created_at DESC, i.id
            """, (project_id,)).fetchall()
        view = self.plans._view(project, plan)
        document = view.plan.document if view.plan else None
        stored = {row["scene_id"]: row for row in rows}
        shots = []
        for scene in document.scenes if document else []:
            row = stored.pop(scene.id, None)
            if row is None:
                shots.append(BoardShot(scene_id=scene.id, title=scene.title))
            else:
                shot = self.summary(row, project["folder"], title=scene.title)
                if shot.status == "review" and row["approved_at"]:
                    shot.status = ("approved" if not plan["stale"] and row["approved_context"] == visual_context(document, scene)
                                   else "changed")
                shots.append(shot)
        # Older plans can be restored through Story plan → Saved versions. Media is always kept.
        off_board = [self.summary(row, project["folder"]) for row in list(stored.values())[:40]]
        return StoryboardView(plan=view, shots=shots, off_board=off_board, off_board_count=len(stored))

    def summary(self, row, folder: str, *, title: str | None = None) -> BoardShot:
        version = self.images.version(row, folder)
        return BoardShot(scene_id=row["scene_id"], title=title or row["title"], revision=row["revision"], active=version,
                         version_count=row["version_count"], status="review" if version.available else "missing")

    def history(self, project_id: str, scene_id: str, before: int | None) -> StillHistory:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project = self.workspace.find_project(db, project_id)
            return self.images.history(db, folder=project["folder"], project_id=project_id, scene_id=scene_id, before=before)

    @staticmethod
    def activate(db, project_id: str, scene: Scene, image_id: str):
        db.execute("""
            INSERT INTO board_shots(project_id, scene_id, title, active_image, revision)
            VALUES (?, ?, ?, ?, 1) ON CONFLICT (project_id, scene_id) DO UPDATE SET title = excluded.title,
               active_image = excluded.active_image, revision = board_shots.revision + 1, approved_at = NULL, approved_context = NULL
        """, (project_id, scene.id, scene.title, image_id))
        PlanStore.touch(db, project_id, timestamp())

    def import_frame(self, project_id: str, scene_id: str, plan_revision: int, shot_revision: int,
                     source: BinaryIO, name: str, credits: Credits) -> StoryboardView:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            project, _, document = self.check_plan(db, project_id, plan_revision)
            self.scene_in(document, scene_id)
            self.check_shot(self.current_shot(db, project_id, scene_id), shot_revision)
        with self.images.prepare(source, name, credits, project_folder=project["folder"]) as image:
            with self.workspace.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                _, _, latest = self.check_plan(db, project_id, plan_revision)
                scene = self.scene_in(latest, scene_id)
                self.check_shot(self.current_shot(db, project_id, scene_id), shot_revision)
                self.images.record(db, image, project_id=project_id, scene_id=scene_id)
                self.activate(db, project_id, scene, image.id)
        return self.view(project_id)

    def choose(self, project_id: str, scene_id: str, request: ChooseFrame) -> StoryboardView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, _, document = self.check_plan(db, project_id, request.plan_revision)
            scene = self.scene_in(document, scene_id)
            row = self.current_shot(db, project_id, scene_id)
            self.check_shot(row, request.shot_revision)
            image = self.check_owner(db, project_id, scene_id, request.image_id)
            if image is None or not self.images.available(image, project["folder"]):
                raise WorkspaceError(404, "That image version is not available for this shot.")
            if row is None or row["active_image"] != image["id"]:
                self.activate(db, project_id, scene, image["id"])
        return self.view(project_id)

    def review(self, project_id: str, request: ShotReview) -> StoryboardView:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            project, plan, document = self.check_plan(db, project_id, request.plan_revision)
            if request.approved and not plan["approved_at"]:
                raise WorkspaceError(409, "Approve the current Story plan before approving frames.")
            choices = []
            for target in request.targets:
                scene = self.scene_in(document, target.scene_id)
                row = self.current_shot(db, project_id, scene.id)
                self.check_shot(row, target.revision)
                if row is None:
                    raise WorkspaceError(422, "Import a still for each selected shot before approving it.")
                context = visual_context(document, scene) if request.approved else None
                if request.approved:
                    image = self.check_owner(db, project_id, scene.id, row["active_image"])
                    if image is None or not self.images.available(image, project["folder"]):
                        raise WorkspaceError(422, "A selected image is missing from disk. Restore the file or import a replacement.")
                if row["approved_context"] != context:
                    choices.append((scene.id, row["active_image"], context))
            # Validate every target before writing; a stale/missing frame can't partially approve a batch.
            if choices:
                now = timestamp()
                for scene_id, image_id, context in choices:
                    db.execute("""
                        UPDATE board_shots SET approved_at = ?, approved_context = ?, revision = revision + 1
                        WHERE project_id = ? AND scene_id = ?
                    """, (now if request.approved else None, context, project_id, scene_id))
                    if request.approved:
                        db.execute("UPDATE studio_images SET last_approved_at = ? WHERE id = ?", (now, image_id))
                self.plans.touch(db, project_id, now)
        return self.view(project_id)
