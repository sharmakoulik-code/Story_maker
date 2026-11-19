"""Single local render worker. FFmpeg receives frames by pipe, never a network input."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from contextlib import suppress
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryFile
from threading import Event, RLock, Thread, Timer
from time import monotonic
from typing import BinaryIO
from uuid import uuid4

from ..hardware import binary, run
from ..images import inside
from ..storage import WorkspaceError, local_path, timestamp
from .engine import FrameRenderer
from .models import FPS, HEIGHT, WIDTH, EncoderMode, ExportJob, ExportRequest, Sequence
from .store import MotionStore

SIZE = f"{2*WIDTH}x{2*HEIGHT}"
ACTIVE = ("queued", "rendering", "cancelling")
HW_ENCODERS = ("h264_qsv", "h264_nvenc", "h264_amf")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class RenderStopped(Exception):
    pass


class EncodeError(Exception):
    pass


def encoding_args(encoder: str) -> list[str]:
    pixel = "nv12" if encoder in ("h264_qsv", "h264_amf") else "yuv420p"
    quality = ["-preset", "veryfast", "-crf", "18", "-threads", "2"] if encoder == "libx264" else []
    return ["-an", "-vf", f"scale=out_color_matrix=bt709:flags=fast_bilinear,format={pixel},setsar=1", "-c:v", encoder,
            *quality, "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


def encoder_choices(ffmpeg: str, mode: EncoderMode) -> list[str]:
    if mode == "software":
        return ["libx264"]
    encoders = run(ffmpeg, "-hide_banner", "-encoders", timeout=5) or ""
    tested = []
    for encoder in HW_ENCODERS:
        if re.search(rf"^\s*V\S*\s+{encoder}\s", encoders, re.M):
            # A compiled encoder is not evidence of a working device/driver. Exercise it at full size.
            if run(ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-filter_threads", "1",
                   "-f", "lavfi", "-i", f"color=s={SIZE}:r={FPS}", "-frames:v", "3",
                   *encoding_args(encoder), "-f", "null", "-", timeout=5) is not None:
                tested.append(encoder)
                break
    return [*tested, "libx264"]


def verify_video(ffprobe: str, path: Path, frames: int) -> None:
    inspected = run(ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_frames,sample_aspect_ratio",
                    "-of", "json", str(path), timeout=10)
    try:
        video = json.loads(inspected or "{}")["streams"][0]
        if (video["codec_name"], video["width"], video["height"], video["pix_fmt"], video["sample_aspect_ratio"]) != (
                "h264", WIDTH*2, HEIGHT*2, "yuv420p", "1:1"):
            raise ValueError
        if Fraction(video["avg_frame_rate"]) != FPS or int(video["nb_frames"]) != frames:
            raise ValueError
    except (ValueError, KeyError, IndexError, ZeroDivisionError, TypeError) as error:
        raise EncodeError("The output did not validate as a 1080 × 1920, 30 FPS H.264 MP4. Check FFmpeg and FFprobe in System & models.") from error


def acquire_lease(path: Path) -> BinaryIO | None:
    """Keep a per-workspace encode lock even if a second studio starts on a different port."""
    handle = None
    try:
        handle = path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError:
        if handle:
            handle.close()
        return None


@dataclass
class Task:
    job_id: str
    final: Path
    ffmpeg: str
    ffprobe: str
    document: Sequence
    files: dict[str, Path]
    mode: EncoderMode
    stop: Event = field(default_factory=Event)
    timed_out: bool = False
    child: subprocess.Popen | None = None
    thread: Thread | None = None

    @property
    def part(self) -> Path:
        return inside(self.final.parent, f".koma-{self.job_id}.part.mp4")


class ExportService:
    def __init__(self, store: MotionStore, *, preview: bool = False) -> None:
        self.store, self.workspace, self.preview = store, store.workspace, preview
        self.lock = RLock()
        self.task: Task | None = None
        self.closing = False
        self.lease: BinaryIO | None = None

    def recover(self) -> None:
        """Interrupted work is never reported as a finished export or silently rerun."""
        self.closing = False
        self.lease = acquire_lease(inside(self.workspace.database.parent, "motion-export.lock"))
        if self.lease is None:
            return
        with self.workspace.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute("SELECT id, folder, filename FROM motion_jobs WHERE state IN ('queued','rendering','cancelling')"):
                try:
                    folder = local_path(row["folder"])
                    inside(folder, f".koma-{row['id']}.part.mp4").unlink(missing_ok=True)
                    inside(folder, row["filename"]).unlink(missing_ok=True)
                except (OSError, ValueError, RuntimeError):
                    pass
            db.execute("""UPDATE motion_jobs SET state = 'failed', message = ?, updated_at = ?
                          WHERE state IN ('queued','rendering','cancelling')""",
                       ("The studio closed before this render finished. Start a new export to retry.", timestamp()))

    def row(self, db, sequence_id: str, job_id: str):
        row = db.execute("SELECT * FROM motion_jobs WHERE id = ? AND sequence_id = ?", (job_id, sequence_id)).fetchone()
        if row is None:
            raise WorkspaceError(404, "That export isn’t in the local timeline.")
        return row

    def summary(self, row) -> ExportJob:
        values = dict(row)
        folder = values.pop("folder")
        available = row["state"] == "complete"
        return ExportJob(**values, output_path=str(Path(folder) / row["filename"]) if available and not self.preview else None)

    def list(self, sequence_id: str) -> list[ExportJob]:
        with self.workspace.connect() as db:
            self.store.find(db, sequence_id)
            rows = db.execute("SELECT * FROM motion_jobs WHERE sequence_id = ? ORDER BY created_at DESC LIMIT 12", (sequence_id,))
            return [self.summary(row) for row in rows]

    def get(self, sequence_id: str, job_id: str) -> ExportJob:
        with self.workspace.connect() as db:
            return self.summary(self.row(db, sequence_id, job_id))

    def file(self, sequence_id: str, job_id: str) -> Path:
        with self.workspace.connect() as db:
            row = self.row(db, sequence_id, job_id)
        try:
            if row["state"] == "complete":
                path = inside(local_path(row["folder"]), row["filename"])
                if path.is_file():
                    return path
        except (OSError, ValueError, RuntimeError):
            pass
        raise WorkspaceError(404, "No finished MP4 is available for this job.")

    def start(self, sequence_id: str, request: ExportRequest) -> ExportJob:
        with self.lock:
            if self.lease is None:
                raise WorkspaceError(409, "Rendering is locked by another studio or the workspace isn’t writable.")
            if self.closing or self.task:
                raise WorkspaceError(409, "A render is already using the encoder on this device. Finish or cancel it first.")
            settings = self.workspace.get_settings()
            ffmpeg = binary("ffmpeg", settings.ffmpeg_path)
            ffprobe = binary("ffprobe", settings.ffprobe_path)
            if not ffmpeg or not ffprobe:
                raise WorkspaceError(422, "Export needs FFmpeg and FFprobe. Add their local executable paths in System & models.")
            try:
                folder = local_path(settings.outputs_dir)
                folder.mkdir(parents=True, exist_ok=True)
                free = shutil.disk_usage(folder).free
            except (OSError, ValueError, RuntimeError) as error:
                raise WorkspaceError(422, "The output folder isn’t available. Check it in System & models.") from error
            with self.workspace.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = self.store.find(db, sequence_id)
                if request.revision != row["revision"]:
                    raise WorkspaceError(409, "This timeline changed. Reopen it and save your edits before exporting.")
                document = Sequence.model_validate_json(row["document"])
                if any(not any(layer.asset for layer in shot.layers) for shot in document.shots):
                    raise WorkspaceError(422, "Add artwork to every shot before exporting.")
                files = self.store.check_assets(db, sequence_id, document)
                if free < 64*1024**2 + document.output_frames // FPS * 2*1024**2:
                    raise WorkspaceError(507, "There isn’t enough free space in the output folder for this export.")
                job_id = uuid4().hex
                slug = re.sub(r"[^a-z0-9]+", "-", document.title.lower()).strip("-")[:55] or "koma-animation"
                filename = f"{slug}-r{request.revision}-{job_id[:10]}.mp4"
                task = Task(job_id, inside(folder, filename), ffmpeg, ffprobe, document, files, request.mode)
                now = timestamp()
                db.execute("""INSERT INTO motion_jobs (id, sequence_id, revision, state, done, frames, encoder, message,
                           folder, filename, created_at, updated_at) VALUES (?, ?, ?, 'queued', 0, ?, NULL, ?, ?, ?, ?, ?)""",
                           (job_id, sequence_id, request.revision, document.output_frames, "Preparing local render…", str(folder), filename, now, now))
                job = self.summary(self.row(db, sequence_id, job_id))
            self.task = task
            task.thread = Thread(target=self.render, args=(task,), name="koma-video-export", daemon=True)
            task.thread.start()
            return job

    def update(self, job_id: str, **values) -> None:
        # Keys below are internal named arguments, never request data.
        values["updated_at"] = timestamp()
        with self.workspace.connect() as db:
            db.execute(f"UPDATE motion_jobs SET {', '.join(f'{key} = ?' for key in values)} WHERE id = ?", (*values.values(), job_id))

    def interrupt(self, task: Task, *, timed_out: bool = False) -> None:
        with self.lock:
            if self.task is not task:
                return
            task.timed_out = timed_out
            task.stop.set()
            if task.child is not None and task.child.poll() is None:
                with suppress(OSError):
                    task.child.kill()  # Unblocks a writer waiting on an FFmpeg pipe, including on Windows.

    def cancel(self, sequence_id: str, job_id: str) -> ExportJob:
        with self.lock:
            current = self.get(sequence_id, job_id)
            if current.state in ACTIVE and self.task and self.task.job_id == job_id:
                self.update(job_id, state="cancelling", message="Stopping the local encoder…")
                self.interrupt(self.task)
            return self.get(sequence_id, job_id)

    def close(self) -> None:
        with self.lock:
            self.closing = True
            task = self.task
            if task:
                self.interrupt(task)
        if task and task.thread:
            task.thread.join(timeout=18)
        with self.lock:
            if self.task is None:
                self.release_lease()

    def release_lease(self) -> None:
        if self.lease is not None:
            self.lease.close()
            self.lease = None

    @staticmethod
    def check_stop(task: Task) -> None:
        if task.stop.is_set():
            raise RenderStopped

    def encode(self, task: Task, encoder: str, part: Path) -> None:
        command = [task.ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-y", "-filter_threads", "1",
                   "-protocol_whitelist", "file,pipe", "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", SIZE,
                   "-framerate", str(FPS), "-i", "pipe:0", *encoding_args(encoder), "-movflags", "+faststart", "-f", "mp4", str(part)]
        with TemporaryFile() as log:
            with self.lock:
                self.check_stop(task)
                proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, creationflags=FLAGS)
                task.child = proc
            try:
                assert proc.stdin is not None
                done, last = 0, monotonic()
                try:
                    for shot in task.document.shots:
                        self.check_stop(task)
                        renderer = FrameRenderer(shot, task.files)
                        for index in range(shot.output_frames):
                            self.check_stop(task)
                            proc.stdin.write(renderer.frame(index).tobytes())
                            done += 1
                            if monotonic() - last >= .4:
                                self.update(task.job_id, done=done)
                                last = monotonic()
                        del renderer
                    proc.stdin.close()
                    if proc.wait(timeout=30) != 0:
                        raise BrokenPipeError
                except (BrokenPipeError, subprocess.TimeoutExpired) as error:
                    self.check_stop(task)
                    log.seek(max(0, log.tell() - 1400))
                    detail = " ".join(log.read().decode("utf-8", "replace").split())[-520:].replace(str(part), "the temporary output")
                    raise EncodeError(f"{encoder} did not finish. {detail or 'Check the local FFmpeg build and output folder.'}") from error
            finally:
                if proc.poll() is None:
                    with suppress(OSError):
                        proc.kill()
                if proc.stdin:
                    with suppress(OSError):
                        proc.stdin.close()
                proc.wait()
                with self.lock:
                    task.child = None

    def render(self, task: Task) -> None:
        timer = Timer(30 * 60, self.interrupt, args=(task,), kwargs={"timed_out": True})
        timer.daemon = True
        timer.start()
        published = False
        part = None
        state, message = "failed", "The local render could not finish."
        try:
            part = task.part
            self.check_stop(task)
            encoders = encoder_choices(task.ffmpeg, task.mode)
            for index, encoder in enumerate(encoders):
                with self.lock:
                    self.check_stop(task)
                    self.update(task.job_id, state="rendering", encoder=encoder, done=0,
                                message="Rendering layers on this device…" if not index else "Hardware encoding failed. Retrying on the CPU…")
                try:
                    self.encode(task, encoder, part)
                    self.check_stop(task)
                    verify_video(task.ffprobe, part, task.document.output_frames)
                    break
                except EncodeError:
                    if index == len(encoders)-1:
                        raise
                    part.unlink(missing_ok=True)
            with self.lock:
                self.check_stop(task)
                if task.final.exists():
                    raise EncodeError("An output with this name already exists. Start a new export.")
                part.replace(task.final)
                try:
                    self.update(task.job_id, state="complete", done=task.document.output_frames, message="MP4 ready to play or download.")
                    published = True
                finally:
                    if not published:
                        task.final.unlink(missing_ok=True)
        except RenderStopped:
            state, message = ("failed", "This render exceeded the 30-minute limit.") if task.timed_out else ("cancelled", "Render cancelled. No partial video was published.")
        except EncodeError as error:
            message = str(error)
        except (OSError, ValueError, RuntimeError):
            message = "Could not render the local artwork or write the MP4. Check the layers, FFmpeg paths and output folder."
        finally:
            timer.cancel()
            if part:
                with suppress(OSError):
                    part.unlink(missing_ok=True)
            with self.lock:
                try:
                    if not published:
                        if task.stop.is_set() and not task.timed_out:
                            state, message = "cancelled", "Render cancelled. No partial video was published."
                        self.update(task.job_id, state=state, message=message)
                finally:
                    self.task = None
                    if self.closing:
                        self.release_lease()
