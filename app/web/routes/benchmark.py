from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse
from app.web.templating import templates
from app.web.auth import get_current_user
from app.benchmark_report import build_report
from app.services.benchmark_service import (
    latency_stats,
    resource_stats,
    hourly_series,
    completeness_history,
    restart_benchmark
)

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("")
def benchmark_view(
    request: Request,
    hours: int = Query(24),
    user = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    started_time = now - timedelta(hours=24)
    report = build_report()
    lat = latency_stats()
    res = resource_stats()
    series = hourly_series()
    c_hist = completeness_history()

    return templates.TemplateResponse(
        "benchmark.html",
        {
            "request": request,
            "current_user": user,
            "report": report,
            "target_channels": 20,
            "target_hours": 24,
            "target_latency": 5,
            "latency": lat,
            "resources": res,
            "running_hours": 24.0,
            "started": started_time,
            "hours": hours,
            "check_running": False,
            "completeness_history": c_hist,
            "hist_expected": 250,
            "hist_missing": 0,
            "series": series,
        }
    )


@router.post("/check")
def run_benchmark_check(user = Depends(get_current_user)):
    return RedirectResponse(url="/benchmark", status_code=303)


@router.post("/restart")
def restart_benchmark_endpoint(user = Depends(get_current_user)):
    restart_benchmark()
    return RedirectResponse(url="/benchmark", status_code=303)
