from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from ..images import MAX_MULTIPART_BYTES
from .export import ExportService
from .models import Asset, ExportJob, ExportRequest, Id, Key, NewSequence, SaveSequence, SequenceSummary, SequenceView
from .store import MotionStore


def motion_routes(store: MotionStore, exports: ExportService) -> APIRouter:
    router = APIRouter(prefix="/api/animation")

    @router.get("", response_model=list[SequenceSummary])
    def list_sequences():
        return store.list()

    @router.post("", response_model=SequenceView, status_code=201)
    def create_sequence(request: NewSequence):
        return store.create(request.title)

    @router.post("/sample", response_model=SequenceView)
    def load_sample():
        return store.create(sample=True)

    @router.get("/art/{key}")
    def original_layer(key: Key):
        return FileResponse(store.builtin(key), media_type="image/webp")

    @router.get("/{sequence_id}", response_model=SequenceView)
    def open_sequence(sequence_id: Id):
        return store.view(sequence_id)

    @router.put("/{sequence_id}", response_model=SequenceView)
    def save_sequence(sequence_id: Id, request: SaveSequence):
        return store.save(sequence_id, request)

    @router.post("/{sequence_id}/assets", response_model=Asset, status_code=201, max_body_size=MAX_MULTIPART_BYTES)
    def import_layer(sequence_id: Id, image: UploadFile):
        return store.import_asset(sequence_id, image.file, image.filename or "")

    @router.get("/{sequence_id}/assets/{key}")
    def layer_image(sequence_id: Id, key: Id):
        return FileResponse(store.get_asset(sequence_id, key), media_type="image/webp")

    @router.get("/{sequence_id}/exports", response_model=list[ExportJob])
    def list_exports(sequence_id: Id):
        return exports.list(sequence_id)

    @router.post("/{sequence_id}/exports", response_model=ExportJob, status_code=202)
    def export(sequence_id: Id, request: ExportRequest):
        return exports.start(sequence_id, request)

    @router.get("/{sequence_id}/exports/{job_id}", response_model=ExportJob)
    def export_status(sequence_id: Id, job_id: Id):
        return exports.get(sequence_id, job_id)

    @router.post("/{sequence_id}/exports/{job_id}/cancel", response_model=ExportJob)
    def cancel_export(sequence_id: Id, job_id: Id):
        return exports.cancel(sequence_id, job_id)

    @router.get("/{sequence_id}/exports/{job_id}/video")
    def watch_export(sequence_id: Id, job_id: Id, download: bool = False):
        path = exports.file(sequence_id, job_id)
        return FileResponse(path, media_type="video/mp4", filename=path.name if download else None)

    return router
