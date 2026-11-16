from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from app.database import SessionLocal
from app.models import SourceChannel


def _v(value: Any, unit: str = "") -> str:
    if value is None:
        return "—"
    if unit:
        return f"{value} {unit}"
    return str(value)


def _verdict(ok: bool) -> str:
    return "ĐẠT" if ok else "CHƯA ĐẠT"


def build_report(
    db=None,
    now: datetime = None,
    started: datetime = None,
    hours_run: float = 0.0,
    lat: Dict[str, Any] = None,
    res: Dict[str, Any] = None,
    history: List[Any] = None,
    series: List[Any] = None,
    sources: List[Any] = None,
    channels: int = 0,
    expected: int = 0,
    missing: int = 0,
    miss_pct: float = 0.0,
    unrecovered: int = 0,
    final_pct: float = 0.0
) -> str:
    """Build markdown report for WP01 Telegram collector benchmark."""
    if now is None:
        now = datetime.now(timezone.utc)
    now_str = now.strftime("%H:%M %d/%m/%Y UTC")
    started_str = started.strftime("%H:%M %d/%m/%Y UTC") if started else "—"

    TARGET_HOURS = 24
    TARGET_CHANNELS = 20
    LATENCY_TARGET_SECONDS = 5.0

    lines = [
        "# BÁO CÁO ĐO KIỂM THỰC TẾ WP01 — BỘ THU THẬP TELEGRAM",
        f"- Thời điểm lập báo cáo: {now_str}",
        f"- Bắt đầu đo: {started_str} — đã chạy **{hours_run:.1f} giờ** / mục tiêu {TARGET_HOURS} giờ",
        f"- Số kênh Telegram đã kết nối: **{_v(channels)}** / mục tiêu {TARGET_CHANNELS}",
        "- Máy chạy: máy Mac nội bộ, SQLite (WAL), một tiến trình uvicorn",
        "",
        "## 1. Kết quả so với tiêu chí",
        "| Tiêu chí | Mục tiêu | Thực tế | Kết luận |",
        "| :--- | :--- | :--- | :---: |",
        f"| Số kênh thực tế | ≥ {TARGET_CHANNELS} | {channels} | {_verdict(channels >= TARGET_CHANNELS)} |",
        f"| Độ trễ phát hiện (trung vị) | < {LATENCY_TARGET_SECONDS} giây | {lat.get('p50', '—') if lat else '—'} s | {_verdict(lat.get('p50', 99) < LATENCY_TARGET_SECONDS if lat else False)} |",
        f"| Tỷ lệ bỏ sót cuối cùng | 0% | {final_pct:.2f}% ({unrecovered} tin) | {_verdict(unrecovered == 0)} |",
        "",
        "## 2. Tài nguyên tiêu thụ",
        "| Chỉ số | Trung bình | Cao nhất |",
        "| :--- | :---: | :---: |",
        f"| CPU | {res.get('cpu_avg', '—') if res else '—'}% | {res.get('cpu_max', '—') if res else '—'}% |",
        f"| RAM | {res.get('ram_avg', '—') if res else '—'} MB | {res.get('ram_max', '—') if res else '—'} MB |"
    ]
    return "\n".join(lines)
