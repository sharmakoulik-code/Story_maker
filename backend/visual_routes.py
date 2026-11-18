from fastapi import APIRouter, Form, Query, UploadFile
from fastapi.responses import FileResponse

from .character_store import CharacterStore
from .images import MAX_MULTIPART_BYTES, ImageStore
from .plan_models import MAX_REVISION, AssetId, CharacterDesign, Key
from .storyboard import StoryboardStore
from .visual_models import (CharacterArchive, CharacterEdit, ChooseFrame, ChooseReference, Credits,
                            LibraryCharacter, ShotReview, StillHistory, StoryboardView)


def visual_routes(images: ImageStore, characters: CharacterStore, storyboard: StoryboardStore) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/images/{image_id}")
    def open_image(image_id: AssetId, thumbnail: bool = False, download: bool = False):
        path = images.get_file(image_id, thumbnail)
        return FileResponse(path, media_type="image/webp", filename=f"koma-still-{image_id[:8]}.webp" if download else None)

    @router.get("/characters", response_model=list[LibraryCharacter])
    def library():
        return characters.list()

    @router.post("/characters", response_model=LibraryCharacter, status_code=201)
    def create_character(design: CharacterDesign):
        return characters.create(design)

    @router.get("/characters/{character_id}", response_model=LibraryCharacter)
    def character(character_id: AssetId):
        return characters.get(character_id)

    @router.put("/characters/{character_id}", response_model=LibraryCharacter)
    def edit_character(character_id: AssetId, request: CharacterEdit):
        return characters.edit(character_id, request.revision, request.design)

    @router.put("/characters/{character_id}/archive", response_model=LibraryCharacter)
    def archive_character(character_id: AssetId, request: CharacterArchive):
        return characters.archive(character_id, request.revision, request.archived)

    @router.get("/characters/{character_id}/references", response_model=StillHistory)
    def reference_history(character_id: AssetId, before: int | None = Query(None, ge=1, le=MAX_REVISION)):
        return characters.history(character_id, before)

    @router.post("/characters/{character_id}/references", response_model=LibraryCharacter, status_code=201, max_body_size=MAX_MULTIPART_BYTES)
    def import_reference(character_id: AssetId, image: UploadFile, revision: int = Form(ge=1, le=MAX_REVISION),
                         source: str = Form("", max_length=300), license_note: str = Form("", max_length=300)):
        return characters.import_reference(character_id, revision, image.file, image.filename or "", Credits(source=source, license_note=license_note))

    @router.put("/characters/{character_id}/reference", response_model=LibraryCharacter)
    def choose_reference(character_id: AssetId, request: ChooseReference):
        return characters.choose_reference(character_id, request.revision, request.image_id)

    @router.get("/projects/{project_id}/storyboard", response_model=StoryboardView)
    def board(project_id: str):
        return storyboard.view(project_id)

    @router.post("/projects/{project_id}/storyboard/review", response_model=StoryboardView)
    def review_frames(project_id: str, request: ShotReview):
        return storyboard.review(project_id, request)

    @router.get("/projects/{project_id}/storyboard/{scene_id}/frames", response_model=StillHistory)
    def frame_history(project_id: str, scene_id: Key, before: int | None = Query(None, ge=1, le=MAX_REVISION)):
        return storyboard.history(project_id, scene_id, before)

    @router.post("/projects/{project_id}/storyboard/{scene_id}/frames", response_model=StoryboardView, status_code=201, max_body_size=MAX_MULTIPART_BYTES)
    def import_frame(project_id: str, scene_id: Key, image: UploadFile,
                     plan_revision: int = Form(ge=1, le=MAX_REVISION), shot_revision: int = Form(ge=0, le=MAX_REVISION),
                     source: str = Form("", max_length=300), license_note: str = Form("", max_length=300)):
        return storyboard.import_frame(project_id, scene_id, plan_revision, shot_revision, image.file, image.filename or "",
                                       Credits(source=source, license_note=license_note))

    @router.put("/projects/{project_id}/storyboard/{scene_id}/frame", response_model=StoryboardView)
    def choose_frame(project_id: str, scene_id: Key, request: ChooseFrame):
        return storyboard.choose(project_id, scene_id, request)

    return router
