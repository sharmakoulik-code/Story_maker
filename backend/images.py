"""Offline still import. Decode bounded raster input and publish two metadata-free local files."""
from __future__ import annotations

import os
import shutil
import sqlite3
import struct
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, ImageOps

from .storage import Workspace, WorkspaceError, local_path, timestamp
from .visual_models import Credits, StillHistory, StillVersion

MAX_IMPORT_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_SIDE = 6000
MAX_MULTIPART_BYTES = MAX_IMPORT_BYTES + 65_536
LENGTH_LIMIT = 16
FORMATS = ("PNG", "JPEG", "WEBP")


def filename_hint(value: str) -> str:
    return "".join(char for char in value.replace("\\", "/").rsplit("/", 1)[-1] if char.isprintable()).strip()[:220] or "Imported image"


def inside(base: Path, *parts: str) -> Path:
    """Only resolve managed media paths. Don't follow redirected files or folders."""
    candidate = base.joinpath(*parts)
    if candidate != candidate.resolve():
        raise ValueError("Managed image paths cannot be redirected.")
    return candidate


def write_image(image: Image.Image, path: Path, *, thumb: bool, lossless: bool = False) -> None:
    with path.open("xb") as stream:
        image.save(stream, format="WEBP", lossless=lossless, method=2, quality=83 if thumb else 94)
        stream.flush()
        os.fsync(stream.fileno())


def encode(source: BinaryIO, directory: Path, *, fit: tuple[int, int] | None = None) -> tuple[int, int, int]:
    source.seek(0, os.SEEK_END)
    if source.tell() > MAX_IMPORT_BYTES:
        raise WorkspaceError(413, "Import a PNG, JPEG, or WebP of 16 MiB or less.")
    source.seek(0)
    try:
        with Image.open(source, formats=FORMATS) as original:
            if max(original.size) > MAX_IMAGE_SIDE or original.width * original.height > MAX_IMAGE_PIXELS:
                raise WorkspaceError(422, "This image is too large. Use at most 12 megapixels and 6,000 pixels on either side.")
            if getattr(original, "n_frames", 1) != 1 or getattr(original, "is_animated", False):
                raise WorkspaceError(422, "Choose a single still image, not an animated file.")
            lossless = original.format != "JPEG"
            original.verify()
        source.seek(0)
        with Image.open(source, formats=FORMATS) as original:
            oriented = ImageOps.exif_transpose(original)
            mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
            clean = oriented.convert(mode)
            clean.info.clear()
    except (OSError, ValueError, SyntaxError, EOFError, struct.error, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise WorkspaceError(422, "Could not read this still image. Choose a valid PNG, JPEG, or WebP.") from error
    with clean:
        if fit:
            clean.thumbnail(fit, Image.Resampling.LANCZOS)
        width, height = clean.size
        full = directory / "image.webp"
        write_image(clean, full, thumb=False, lossless=lossless)
        clean.thumbnail((360, 640), Image.Resampling.LANCZOS)
        write_image(clean, directory / "thumb.webp", thumb=True)
    return width, height, full.stat().st_size


@dataclass
class StagedImage:
    id: str
    staging: Path
    destination: Path
    name: str
    credits: Credits
    width: int
    height: int
    bytes: int
    published: bool = False

    def publish(self) -> None:
        # Only publish a unique new version, never overwrite a previous image.
        if self.destination.exists():
            raise OSError("Image ID already used")
        self.staging.rename(self.destination)
        self.published = True


class ImageStore:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.preparing = Lock()

    def root(self, *, project_folder: str | None = None, character_id: str | None = None) -> Path:
        if project_folder is not None:
            folder = local_path(project_folder)
            if folder != Path(project_folder) or not folder.is_dir():
                raise ValueError("Project folder is unavailable.")
            return inside(folder, "stills")
        if character_id is None:
            raise ValueError("No image owner.")
        return inside(self.workspace.base, "characters", character_id, "references")

    @contextmanager
    def prepare(self, source: BinaryIO, name: str, credits: Credits, *, project_folder: str | None = None, character_id: str | None = None):
        if not self.preparing.acquire(blocking=False):
            raise WorkspaceError(429, "Another image is being imported. Try again once it finishes.")
        try:
            root = self.root(project_folder=project_folder, character_id=character_id)
            root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".import-", dir=root) as temporary:
                image_id = uuid4().hex
                staging = Path(temporary) / image_id
                staging.mkdir()
                width, height, size = encode(source, staging)
                item = StagedImage(image_id, staging, inside(root, image_id), filename_hint(name), credits, width, height, size)
                try:
                    yield item
                except BaseException:
                    if item.published:
                        with suppress(OSError):
                            shutil.rmtree(item.destination)
                    raise
        except sqlite3.OperationalError as error:
            raise WorkspaceError(503, "Could not commit the image to the local library. Reopen the board or character and try again.") from error
        except (OSError, ValueError, RuntimeError) as error:
            raise WorkspaceError(422, "Could not save this image. Check that the local folder is available, writable, and has free space.") from error
        finally:
            self.preparing.release()

    @staticmethod
    def record(db: sqlite3.Connection, image: StagedImage, *, project_id: str | None = None,
               scene_id: str | None = None, character_id: str | None = None) -> None:
        condition, params = (("character_id = ?", (character_id,)) if character_id is not None else
                             ("project_id = ? AND scene_id = ?", (project_id, scene_id)))
        number = db.execute(f"SELECT coalesce(max(number), 0) + 1 FROM studio_images WHERE {condition}", params).fetchone()[0]
        image.publish()
        db.execute("""
            INSERT INTO studio_images (id, project_id, scene_id, character_id, number, original_name, source,
                license_note, width, height, bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (image.id, project_id, scene_id, character_id, number, image.name, image.credits.source or "Local file",
              image.credits.license_note or "Not specified", image.width, image.height, image.bytes, timestamp()))

    def path(self, row: sqlite3.Row, folder: str | None, thumbnail: bool = False) -> Path:
        root = self.root(project_folder=folder, character_id=row["character_id"])
        return inside(root, row["id"], "thumb.webp" if thumbnail else "image.webp")

    def available(self, row: sqlite3.Row, folder: str | None) -> bool:
        try:
            full = self.path(row, folder)
            return full.is_file() and full.stat().st_size == row["bytes"]
        except (OSError, ValueError, RuntimeError):
            return False

    def version(self, row: sqlite3.Row, folder: str | None) -> StillVersion:
        values = {key: row[key] for key in ("id", "number", "original_name", "source", "license_note", "width",
                                             "height", "bytes", "created_at", "last_approved_at")}
        return StillVersion(**values, available=self.available(row, folder))

    def history(self, db, *, folder: str | None = None, project_id: str | None = None,
                scene_id: str | None = None, character_id: str | None = None, before: int | None = None) -> StillHistory:
        condition, params = (("character_id = ?", (character_id,)) if character_id is not None else
                             ("project_id = ? AND scene_id = ?", (project_id, scene_id)))
        if before is not None:
            condition += " AND number < ?"
            params += (before,)
        rows = db.execute(f"SELECT * FROM studio_images WHERE {condition} ORDER BY number DESC LIMIT ?",
                          (*params, LENGTH_LIMIT + 1)).fetchall()
        return StillHistory(versions=[self.version(row, folder) for row in rows[:LENGTH_LIMIT]],
                            next_before=rows[LENGTH_LIMIT - 1]["number"] if len(rows) > LENGTH_LIMIT else None)

    def get_file(self, image_id: str, thumbnail: bool) -> Path:
        with self.workspace.connect() as db:
            row = db.execute("""
                SELECT i.*, p.folder FROM studio_images AS i LEFT JOIN projects AS p ON i.project_id = p.id WHERE i.id = ?
            """, (image_id,)).fetchone()
        try:
            if row is not None and self.available(row, row["folder"]):
                path = self.path(row, row["folder"], thumbnail)
                if thumbnail and not path.is_file():
                    path = self.path(row, row["folder"])
                return path
        except (OSError, ValueError, RuntimeError):
            pass
        raise WorkspaceError(404, "That image is not available in the local workspace.")
