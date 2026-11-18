from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Path as ApiPath, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles

from . import VERSION
from .character_store import CharacterStore
from .demo import seed_preview
from .hardware import HardwareMonitor
from .images import ImageStore
from .plan_models import (MAX_REVISION, AdoptTarget, GeneratePlan, PlanApproval, PlanHistory,
                          PlanVersion, PlanView, RestoreVersion, SavePlan)
from .plan_store import PlanStore
from .schemas import ArchiveState, Draft, Project, ProjectSummary, Settings, SettingsView
from .storage import Workspace, WorkspaceError, default_data_dir
from .storyboard import StoryboardStore
from .visual_routes import visual_routes


FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "dist"
LOCAL_HOST = re.compile(r"(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?", re.I)
PREVIEW_HOST = re.compile(r"[0-9]{1,5}-[a-z0-9-]+\.e2b\.app", re.I)


def create_app(data_dir: Path | None = None, *, preview: bool = False, frontend: Path = FRONTEND) -> FastAPI:
    workspace = Workspace(data_dir if data_dir is not None else default_data_dir())
    hardware = HardwareMonitor()
    plans = PlanStore(workspace)
    images = ImageStore(workspace)
    characters = CharacterStore(workspace, images)
    storyboard = StoryboardStore(workspace, plans, images)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        workspace.initialize()
        if preview:
            seed_preview(workspace, plans, characters, storyboard)
        await asyncio.to_thread(hardware.read, workspace.base, workspace.get_settings())
        yield

    app = FastAPI(
        title="Koma Studio", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
        max_body_size=1_500_000,
        telemetry={"tracing": False, "metrics": False, "logs": False, "auto_configure": False},
    )

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        proxied = request.headers.get("x-forwarded-host", "").lower()
        if not LOCAL_HOST.fullmatch(host) and not (preview and PREVIEW_HOST.fullmatch(host)):
            return PlainTextResponse("This host is not allowed.", status_code=400)
        origin = request.headers.get("origin")
        allowed_origins = {f"http://{host}"} if LOCAL_HOST.fullmatch(host) else {f"https://{host}"}
        if preview and LOCAL_HOST.fullmatch(host) and PREVIEW_HOST.fullmatch(proxied):
            allowed_origins.add(f"https://{proxied}")
        path = request.url.path
        is_api = path == "/api" or path.startswith("/api/")
        if is_api and ((origin is not None and origin not in allowed_origins)
                       or request.headers.get("sec-fetch-site") not in (None, "none", "same-origin")):
            return PlainTextResponse("Cross-origin requests to the local studio are not allowed.", status_code=403)

        response = await call_next(request)
        rules = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                 "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
                 "base-uri 'none'; form-action 'self'")
        response.headers["Content-Security-Policy"] = rules if preview else f"{rules}; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if is_api or not path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(WorkspaceError)
    async def workspace_error(_: Request, error: WorkspaceError):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        # Do not reflect story text or request bodies back in validation responses.
        detail = [{"field": ".".join(str(location) for location in item["loc"] if location != "body"), "message": item["msg"]}
                  for item in error.errors()]
        return JSONResponse({"detail": detail}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"app": "koma-studio", "version": VERSION, "mode": "preview" if preview else "local"}

    @app.get("/api/hardware")
    def hardware_report(refresh: bool = False):
        return hardware.read(workspace.base, workspace.get_settings(), refresh=refresh)

    @app.get("/api/settings", response_model=SettingsView)
    def settings_view() -> SettingsView:
        return SettingsView(values=workspace.get_settings(), defaults=workspace.defaults,
                            data_dir=str(workspace.base), editable=not preview)

    @app.put("/api/settings", response_model=SettingsView)
    def update_settings(settings: Settings) -> SettingsView:
        if preview:
            raise WorkspaceError(403, "Device paths are read-only in the demo preview. Use the Windows launcher to edit local folders.")
        workspace.save_settings(settings)
        return settings_view()

    @app.get("/api/projects", response_model=list[ProjectSummary])
    def list_projects():
        return workspace.list_projects()

    @app.post("/api/projects", response_model=Project, status_code=201)
    def create_project(draft: Draft):
        return workspace.create_project(draft)

    @app.get("/api/projects/{project_id}", response_model=Project)
    def get_project(project_id: str):
        return workspace.get_project(project_id)

    @app.put("/api/projects/{project_id}", response_model=Project)
    def edit_project(project_id: str, draft: Draft):
        return workspace.update_project(project_id, draft)

    @app.put("/api/projects/{project_id}/archive", response_model=Project)
    def archive_project(project_id: str, state: ArchiveState):
        return workspace.set_archived(project_id, state.archived)

    @app.get("/api/projects/{project_id}/plan", response_model=PlanView)
    def story_plan(project_id: str):
        return plans.view(project_id)

    @app.post("/api/projects/{project_id}/plan", response_model=PlanView)
    def generate_story_plan(project_id: str, request: GeneratePlan):
        return plans.generate(project_id, request.expected_revision)

    @app.put("/api/projects/{project_id}/plan", response_model=PlanView)
    def save_story_plan(project_id: str, request: SavePlan):
        return plans.save(project_id, request)

    @app.put("/api/projects/{project_id}/plan/approval", response_model=PlanView)
    def approve_story_plan(project_id: str, request: PlanApproval):
        return plans.approve(project_id, request.revision, request.approved)

    @app.put("/api/projects/{project_id}/plan/target", response_model=PlanView)
    def adopt_story_target(project_id: str, request: AdoptTarget):
        return plans.adopt_target(project_id, request.revision)

    @app.get("/api/projects/{project_id}/plan/history", response_model=PlanHistory)
    def story_plan_history(project_id: str, before: int | None = Query(default=None, ge=1, le=MAX_REVISION)):
        return plans.history(project_id, before)

    @app.get("/api/projects/{project_id}/plan/history/{revision}", response_model=PlanVersion)
    def download_plan_version(project_id: str, response: Response, revision: int = ApiPath(ge=1, le=MAX_REVISION)):
        version = plans.version(project_id, revision)
        response.headers["Content-Disposition"] = f'attachment; filename="koma-plan-revision-{version.revision}.json"'
        return version

    @app.put("/api/projects/{project_id}/plan/restore", response_model=PlanView)
    def restore_plan_version(project_id: str, request: RestoreVersion):
        return plans.restore(project_id, request.revision, request.version)

    app.include_router(visual_routes(images, characters, storyboard))

    for folder in ("assets", "licenses"):
        if (frontend / folder).is_dir():
            app.mount(f"/{folder}", StaticFiles(directory=frontend / folder), name=folder)

    @app.api_route("/{page:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def studio(page: str):
        if page == "api" or page.startswith(("api/", "assets/")):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        if page == "koma.svg" and (frontend / page).is_file():
            return FileResponse(frontend / page, media_type="image/svg+xml")
        if not (frontend / "index.html").is_file():
            return PlainTextResponse("The studio UI has not been built. Run setup.bat or see README.md.", status_code=503)
        return FileResponse(frontend / "index.html", media_type="text/html")

    return app
