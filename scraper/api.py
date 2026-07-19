from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from auth import require_dashboard_auth
from models import Job, JobCreate, PageRow

router = APIRouter(dependencies=[Depends(require_dashboard_auth)])

_DASHBOARD = Path(__file__).parent / "static" / "dashboard.html"


@router.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(_DASHBOARD)


@router.post("/jobs")
async def create_job(body: JobCreate, request: Request) -> Job:
    return await request.app.state.store.create_job(body)


@router.get("/jobs")
async def list_jobs(request: Request, limit: int = 50) -> list[Job]:
    return await request.app.state.store.list_jobs(limit)


@router.get("/jobs/{id}")
async def get_job(id: int, request: Request) -> Job:
    job = await request.app.state.store.get_job(id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{id}/pages")
async def list_pages(
    id: int, request: Request, status: str | None = None, limit: int = 100
) -> list[PageRow]:
    return await request.app.state.store.list_pages(id, status, limit)


@router.post("/jobs/{id}/cancel")
async def cancel_job(id: int, request: Request) -> Job:
    job = await request.app.state.store.cancel_job(id)
    if job is None:
        raise HTTPException(status_code=409, detail="Job not found or already finished")
    return job


@router.post("/jobs/{id}/retry-failed")
async def retry_failed(id: int, request: Request) -> dict:
    if await request.app.state.store.get_job(id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    requeued = await request.app.state.store.retry_failed(id)
    return {"requeued": requeued}
