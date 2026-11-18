from __future__ import annotations

import sqlite3
from typing import BinaryIO
from uuid import uuid4

from .images import ImageStore
from .plan_models import CharacterDesign
from .storage import Workspace, WorkspaceError, timestamp
from .visual_models import Credits, LibraryCharacter, StillHistory


class CharacterStore:
    def __init__(self, workspace: Workspace, images: ImageStore):
        self.workspace = workspace
        self.images = images

    @staticmethod
    def find(db: sqlite3.Connection, character_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM cast_library WHERE id = ?", (character_id,)).fetchone()
        if row is None:
            raise WorkspaceError(404, "This character is not in the library.")
        return row

    @classmethod
    def check(cls, db, character_id: str, revision: int, *, allow_archived: bool = False):
        row = cls.find(db, character_id)
        if row["revision"] != revision:
            raise WorkspaceError(409, "This library character changed. Reopen it and try again.")
        if row["archived_at"] and not allow_archived:
            raise WorkspaceError(409, "Restore this character before editing its design or reference.")
        return row

    def view(self, db, row: sqlite3.Row) -> LibraryCharacter:
        reference = db.execute("SELECT * FROM studio_images WHERE id = ?", (row["active_reference"],)).fetchone()
        count = db.execute("SELECT count(*) FROM studio_images WHERE character_id = ?", (row["id"],)).fetchone()[0]
        return LibraryCharacter(id=row["id"], revision=row["revision"], design=CharacterDesign.model_validate_json(row["design"]),
                                created_at=row["created_at"], updated_at=row["updated_at"], archived_at=row["archived_at"],
                                reference=self.images.version(reference, None) if reference is not None else None,
                                reference_count=count)

    def list(self) -> list[LibraryCharacter]:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            return [self.view(db, row) for row in db.execute("SELECT * FROM cast_library ORDER BY updated_at DESC, id").fetchall()]

    def get(self, character_id: str) -> LibraryCharacter:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            return self.view(db, self.find(db, character_id))

    def create(self, design: CharacterDesign) -> LibraryCharacter:
        key, now = uuid4().hex, timestamp()
        with self.workspace.connect() as db:
            db.execute("INSERT INTO cast_library(id, design, revision, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                       (key, design.model_dump_json(), now, now))
            return self.view(db, self.find(db, key))

    def edit(self, character_id: str, revision: int, design: CharacterDesign) -> LibraryCharacter:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.check(db, character_id, revision)
            if design != CharacterDesign.model_validate_json(row["design"]):
                db.execute("UPDATE cast_library SET design = ?, revision = revision + 1, updated_at = ? WHERE id = ?",
                           (design.model_dump_json(), timestamp(), character_id))
                row = self.find(db, character_id)
            return self.view(db, row)

    def archive(self, character_id: str, revision: int, archived: bool) -> LibraryCharacter:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.check(db, character_id, revision, allow_archived=True)
            if bool(row["archived_at"]) != archived:
                now = timestamp()
                db.execute("UPDATE cast_library SET archived_at = ?, revision = revision + 1, updated_at = ? WHERE id = ?",
                           (now if archived else None, now, character_id))
                row = self.find(db, character_id)
            return self.view(db, row)

    def history(self, character_id: str, before: int | None) -> StillHistory:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            self.find(db, character_id)
            return self.images.history(db, character_id=character_id, before=before)

    @staticmethod
    def activate(db, character_id: str, image_id: str):
        db.execute("UPDATE cast_library SET active_reference = ?, revision = revision + 1, updated_at = ? WHERE id = ?",
                   (image_id, timestamp(), character_id))

    def import_reference(self, character_id: str, revision: int, source: BinaryIO, name: str, credits: Credits) -> LibraryCharacter:
        with self.workspace.connect() as db:
            self.check(db, character_id, revision)
        with self.images.prepare(source, name, credits, character_id=character_id) as image:
            with self.workspace.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                self.check(db, character_id, revision)
                self.images.record(db, image, character_id=character_id)
                self.activate(db, character_id, image.id)
        return self.get(character_id)

    def choose_reference(self, character_id: str, revision: int, image_id: str) -> LibraryCharacter:
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.check(db, character_id, revision)
            image = db.execute("SELECT * FROM studio_images WHERE id = ? AND character_id = ?", (image_id, character_id)).fetchone()
            if image is None or not self.images.available(image, None):
                raise WorkspaceError(404, "That reference is not available for this character.")
            if row["active_reference"] != image_id:
                self.activate(db, character_id, image_id)
            return self.view(db, self.find(db, character_id))
