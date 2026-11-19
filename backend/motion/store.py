from __future__ import annotations

from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from uuid import uuid4
from contextlib import suppress
import shutil

from PIL import Image

from ..images import encode, filename_hint, inside
from ..storage import Workspace, WorkspaceError, timestamp
from .models import MAX_ASSETS, MAX_SHOT_PIXELS, Asset, SaveSequence, Sequence, SequenceSummary, SequenceView, Shot
from .sample import ART, blue_flower


class MotionStore:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.import_lock = Lock()

    @cached_property
    def artwork(self) -> dict[str, Asset]:
        items = {}
        for path in sorted(ART.glob("bf-*.webp")):
            with Image.open(path, formats=("WEBP",)) as image:
                items[path.stem] = Asset(id=path.stem, name=path.stem.removeprefix("bf-").replace("-", " ").capitalize(),
                                         width=image.width, height=image.height, url=f"/api/animation/art/{path.stem}")
        return items

    def find(self, db, sequence_id: str):
        row = db.execute("SELECT * FROM motion_sequences WHERE id = ?", (sequence_id,)).fetchone()
        if row is None:
            raise WorkspaceError(404, "This animation isn’t in the local library.")
        return row

    @staticmethod
    def summary(row) -> SequenceSummary:
        return SequenceSummary(id=row["id"], title=row["title"], revision=row["revision"], sample=row["sample_key"] is not None,
                               frames=row["frames"], shots=row["shots"], updated_at=row["updated_at"])

    def catalog(self, db, sequence_id: str) -> dict[str, Asset]:
        items = dict(self.artwork)
        for row in db.execute("SELECT id, name, width, height FROM motion_assets WHERE sequence_id = ? ORDER BY name", (sequence_id,)):
            items[row["id"]] = Asset(**dict(row), url=f"/api/animation/{sequence_id}/assets/{row['id']}")
        return items

    def check_assets(self, db, sequence_id: str, document: Sequence) -> dict[str, Path]:
        assets = self.catalog(db, sequence_id)
        files = {}
        for shot in document.shots:
            refs = {layer.asset for layer in shot.layers if layer.asset}
            if not refs <= assets.keys():
                raise WorkspaceError(422, "A layer refers to an image outside this timeline’s library.")
            if sum(assets[key].width * assets[key].height for key in refs) > MAX_SHOT_PIXELS:
                raise WorkspaceError(422, "This shot has over 12 megapixels of source artwork. Split the shot or import smaller cropped layers.")
            for key in refs:
                files[key] = self.file(sequence_id, key)
        return files

    def list(self) -> list[SequenceSummary]:
        with self.workspace.connect() as db:
            return [self.summary(row) for row in db.execute("SELECT * FROM motion_sequences ORDER BY updated_at DESC, id")]

    def view(self, sequence_id: str) -> SequenceView:
        with self.workspace.connect() as db:
            db.execute("BEGIN")
            row = self.find(db, sequence_id)
            return SequenceView(**self.summary(row).model_dump(), document=Sequence.model_validate_json(row["document"]),
                                assets=list(self.catalog(db, sequence_id).values()))

    def create(self, title: str = "", *, sample: bool = False) -> SequenceView:
        sequence_id = uuid4().hex
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM motion_sequences WHERE sample_key = 'blue-flower'").fetchone() if sample else None
            if existing:
                sequence_id = existing["id"]
            else:
                document = blue_flower() if sample else Sequence(title=title, shots=[Shot(id="shot-1", name="First shot")])
                self.check_assets(db, sequence_id, document)
                db.execute("""INSERT INTO motion_sequences (id, sample_key, revision, title, frames, shots, document, updated_at)
                              VALUES (?, ?, 1, ?, ?, ?, ?, ?)""", (sequence_id, "blue-flower" if sample else None, document.title,
                              document.output_frames, len(document.shots), document.model_dump_json(), timestamp()))
        return self.view(sequence_id)

    def save(self, sequence_id: str, change: SaveSequence) -> SequenceView:
        document = change.document
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self.find(db, sequence_id)
            if change.revision != current["revision"]:
                raise WorkspaceError(409, "This timeline changed in another window. Reopen it before saving.")
            self.check_assets(db, sequence_id, document)
            text = document.model_dump_json()
            if text != current["document"]:
                db.execute("""UPDATE motion_sequences SET revision = revision + 1, title = ?, frames = ?, shots = ?,
                              document = ?, updated_at = ? WHERE id = ?""", (document.title, document.output_frames, len(document.shots),
                              text, timestamp(), sequence_id))
        return self.view(sequence_id)

    def file(self, sequence_id: str, key: str) -> Path:
        try:
            path = inside(ART, f"{key}.webp") if key in self.artwork else inside(self.workspace.base, "animation", sequence_id, "assets", key, "image.webp")
            if path.is_file():
                return path
        except (OSError, ValueError, RuntimeError):
            pass
        raise WorkspaceError(404, "A layer’s artwork is unavailable in the local library.")

    def get_asset(self, sequence_id: str, key: str) -> Path:
        with self.workspace.connect() as db:
            self.find(db, sequence_id)
            if db.execute("SELECT id FROM motion_assets WHERE sequence_id = ? AND id = ?", (sequence_id,key)).fetchone() is None:
                raise WorkspaceError(404, "This layer image isn’t in the animation’s library.")
        return self.file(sequence_id, key)

    def builtin(self, key: str) -> Path:
        if key not in self.artwork:
            raise WorkspaceError(404, "This sample asset is unavailable.")
        return self.file("", key)

    def import_asset(self, sequence_id: str, stream, filename: str) -> Asset:
        if not self.import_lock.acquire(blocking=False):
            raise WorkspaceError(429, "Another layer is being imported. Try again after it finishes.")
        try:
            with self.workspace.connect() as db:
                self.find(db, sequence_id)
                if db.execute("SELECT count(*) FROM motion_assets WHERE sequence_id = ?", (sequence_id,)).fetchone()[0] >= MAX_ASSETS:
                    raise WorkspaceError(422, "This timeline has reached its 72 imported artwork limit.")
            root = inside(self.workspace.base, "animation", sequence_id, "assets")
            root.mkdir(parents=True, exist_ok=True)
            key = uuid4().hex
            name = filename_hint(filename)
            with TemporaryDirectory(prefix=".import-", dir=root) as tmp:
                staged = Path(tmp) / key
                staged.mkdir()
                w, h, _ = encode(stream, staged, fit=(1080, 1920))
                dest = inside(root, key)
                staged.rename(dest)
                try:
                    with self.workspace.connect() as db:
                        db.execute("INSERT INTO motion_assets (id, sequence_id, name, width, height) VALUES (?, ?, ?, ?, ?)",
                                   (key, sequence_id, name, w, h))
                except BaseException:
                    with suppress(OSError):
                        shutil.rmtree(dest)
                    raise
            return Asset(id=key, name=name, width=w, height=h, url=f"/api/animation/{sequence_id}/assets/{key}")
        except (OSError, ValueError, RuntimeError) as error:
            raise WorkspaceError(422, "Could not save this layer. Check the local workspace permissions and free space.") from error
        finally:
            self.import_lock.release()
