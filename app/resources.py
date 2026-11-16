import sys
from pathlib import Path

def get_base_dir() -> Path:
    """Return sys._MEIPASS if running in a PyInstaller bundle, else project root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def get_asset_path(relative_path: str) -> Path:
    """Resolve an asset path reliably in both dev and packaged modes."""
    base = get_base_dir()
    p = base / relative_path
    if p.exists():
        return p
    # Fallback to local cwd
    local_p = Path(relative_path)
    if local_p.exists():
        return local_p
    return p
