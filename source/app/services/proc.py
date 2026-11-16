"""Subprocess runner with security and windowless support."""

import os
import sys
import subprocess
from typing import Optional, List, Union

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run(cmd: Union[str, List[str]], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    if "capture_output" not in kwargs and "stdout" not in kwargs and "stderr" not in kwargs:
        kwargs["capture_output"] = True
    return subprocess.run(cmd, **kwargs)


def tool_error(tool_name: str, res: subprocess.CompletedProcess) -> Optional[str]:
    if res.returncode != 0:
        return f"Máy không chạy được {tool_name} (mã {res.returncode}): {res.stderr.strip() if res.stderr else 'Không rõ lỗi'}"
    return None
