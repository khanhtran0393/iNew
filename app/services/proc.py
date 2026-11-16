import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List, Any, Tuple

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")

# Check if bundled ffmpeg exists
_possible_ffmpeg = [
    Path(__file__).resolve().parent.parent.parent / "ffmpeg" / "ffmpeg.exe",
    Path(sys.executable).parent / "ffmpeg.exe",
    Path(__file__).resolve().parent.parent.parent / "bin" / "ffmpeg.exe",
    Path(__file__).resolve().parent.parent.parent / "ffmpeg.exe",
]
for p in _possible_ffmpeg:
    if p.exists():
        FFMPEG_BIN = str(p)
        break

_possible_ffprobe = [
    Path(__file__).resolve().parent.parent.parent / "ffmpeg" / "ffprobe.exe",
    Path(sys.executable).parent / "ffprobe.exe",
    Path(__file__).resolve().parent.parent.parent / "bin" / "ffprobe.exe",
    Path(__file__).resolve().parent.parent.parent / "ffprobe.exe",
]
for p in _possible_ffprobe:
    if p.exists():
        FFPROBE_BIN = str(p)
        break


def blocked_message(tool: str, error: Exception) -> str:
    return (
        f"Máy không chạy được {tool} (công cụ âm thanh/video đi kèm iNew): {error}. "
        "Phần mềm diệt virus hoặc chính sách bảo mật của máy có thể đã chặn tệp này: "
        "hãy cho phép thư mục cài iNew rồi thử lại, hoặc cài lại iNew."
    )


def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Safely execute command with hidden console window and standard encoding."""
    if sys.platform == "win32":
        flags = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
        kwargs["creationflags"] = flags

    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    kwargs.setdefault("capture_output", True)

    try:
        return subprocess.run(cmd, **kwargs)
    except OSError as e:
        tool_name = Path(cmd[0]).name if cmd else "Công cụ"
        raise RuntimeError(blocked_message(tool_name, e)) from e


async def run_process_async(cmd: List[str], **kwargs) -> Tuple[int, str, str]:
    """Execute asynchronous subprocess with hidden console window."""
    flags = kwargs.pop("creationflags", 0)
    if sys.platform == "win32":
        flags |= CREATE_NO_WINDOW

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=flags,
            **kwargs
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return proc.returncode, stdout, stderr
    except OSError as e:
        tool_name = Path(cmd[0]).name if cmd else "Công cụ"
        raise RuntimeError(blocked_message(tool_name, e)) from e
