"""System status and diagnostics API routes."""

from fastapi import APIRouter
from app.services.diagnostics import get_system_diagnostics

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status():
    return get_system_diagnostics()
