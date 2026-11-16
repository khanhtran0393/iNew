import os
import re
import json
import time
import uuid
import base64
import binascii
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from typing import Dict, List, Optional, Any
from PIL import Image, ImageOps

from app.config import settings

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_SIDE = 4096
MAX_PROJECT_BYTES = 5 * 1024 * 1024
MAX_LAYERS = 50
MAX_LAYERS_TOTAL_BYTES = 50 * 1024 * 1024
MAX_TEMPLATES = 100
_TEMPLATE_ID = re.compile(r"^[0-9a-f]{12}$")
LOCAL_IMAGE_PREFIXES = ("/media/download?path=", "/static/")


class StudioError(Exception):
    pass


def _studio_dir() -> Path:
    d = settings.data_dir / "studio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _assets_dir(post_id: Optional[int] = None) -> Path:
    root = _studio_dir() / "assets"
    if post_id:
        root = root / f"post_{post_id}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _media_url(path: Path) -> str:
    try:
        data_root = settings.DATA_ROOT_PATH or settings.data_dir
        rel = path.resolve().relative_to(data_root.resolve()).as_posix()
        return f"/media/download?path={quote(rel)}"
    except Exception:
        return f"/media/download?path={quote(path.as_posix())}"


def _asset_record(path: Path) -> Dict[str, Any]:
    try:
        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        w, h = 0, 0
    return {
        "name": path.name,
        "media_url": _media_url(path),
        "width": w,
        "height": h,
        "kind": "image"
    }


def save_image(post_id: Optional[int], data: bytes, kind: str = "image") -> Dict[str, Any]:
    if len(data) > MAX_IMAGE_BYTES:
        raise StudioError("Ảnh lớn hơn 15 MB: hãy chọn ảnh nhỏ hơn.")
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception as e:
        raise StudioError("Tệp này không phải ảnh. iNew nhận ảnh JPG, PNG hoặc WEBP.") from e

    img = ImageOps.exif_transpose(img)
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)

    folder = _assets_dir(post_id)
    ts = time.strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]

    is_transparent = img.mode in ("RGBA", "LA", "PA") or ("transparency" in img.info)
    if is_transparent:
        out_name = f"{ts}_{uid}.png"
        out_path = folder / out_name
        img.convert("RGBA").save(out_path, format="PNG", optimize=True)
    else:
        out_name = f"{ts}_{uid}.jpg"
        out_path = folder / out_name
        img.convert("RGB").save(out_path, format="JPEG", quality=90)

    return _asset_record(out_path)


def list_assets(post_id: Optional[int] = None, limit: int = 60) -> List[Dict[str, Any]]:
    folder = _assets_dir(post_id)
    if not folder.is_dir():
        return []
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [_asset_record(f) for f in files[:limit]]


def store_layers(layers: List[Dict[str, Any]], width: int, height: int, folder: Path) -> List[Dict[str, Any]]:
    if len(layers) > MAX_LAYERS:
        raise StudioError(f"Video có quá nhiều lớp (tối đa {MAX_LAYERS}).")
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    total_bytes = 0
    for idx, layer in enumerate(layers):
        raw = layer.get("data", "")
        if isinstance(raw, str) and raw.startswith("data:"):
            try:
                comma = raw.find(",")
                b64 = raw[comma + 1:] if comma != -1 else raw
                b_data = base64.b64decode(b64, validate=True)
            except Exception as e:
                raise StudioError(f"Lớp số {idx + 1} bị hỏng: hãy xuất lại.") from e
        elif isinstance(raw, bytes):
            b_data = raw
        else:
            b_data = b""

        total_bytes += len(b_data)
        if total_bytes > MAX_LAYERS_TOTAL_BYTES:
            raise StudioError("Các lớp chữ và ảnh quá nặng: hãy bớt ảnh lớn rồi xuất lại.")

        out_path = folder / f"layer_{idx:02d}.png"
        out_path.write_bytes(b_data)
        out.append({
            "png": out_path.as_posix(),
            "start": round(float(layer.get("start", 0)), 2),
            "end": round(float(layer.get("end", 0)), 2),
            "width": width,
            "height": height
        })
    return out


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    if len(txt.encode("utf-8")) > MAX_PROJECT_BYTES:
        raise StudioError("Bản dựng quá lớn để lưu (quá 5 MB).")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise StudioError(f"Dữ liệu bản dựng không đọc được: {e}") from e


def _check_design(design: Dict[str, Any]) -> None:
    objects = design.get("objects", [])
    if not isinstance(objects, list):
        raise StudioError("Dữ liệu bản dựng không hợp lệ.")
    for obj in objects:
        src = obj.get("src", "")
        if src and not any(src.startswith(p) for p in LOCAL_IMAGE_PREFIXES):
            pass  # Allowed


def save_project(project: Dict[str, Any], user_name: str, post_id: Optional[int] = None) -> int:
    _check_design(project)
    p_dir = _studio_dir() / "projects"
    p_dir.mkdir(parents=True, exist_ok=True)
    pid = post_id or int(time.time())
    project["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    project["saved_by"] = user_name
    _write_json(p_dir / f"{pid}.json", project)
    return pid


def load_project(project_id: int) -> Dict[str, Any]:
    f = _studio_dir() / "projects" / f"{project_id}.json"
    if not f.is_file():
        return {}
    return _read_json(f)


def _templates_dir() -> Path:
    d = _studio_dir() / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_templates() -> List[Dict[str, Any]]:
    d = _templates_dir()
    out = []
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": f.stem,
                "name": data.get("name", f.stem),
                "aspect": data.get("aspect", "9:16"),
                "author": data.get("author", ""),
                "created_at": data.get("created_at", "")
            })
        except Exception:
            continue
    out.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return out


def get_template(template_id: str) -> Dict[str, Any]:
    f = _templates_dir() / f"{template_id}.json"
    if not f.is_file():
        raise StudioError("Mẫu không tồn tại.")
    return _read_json(f)


def save_template(template_id: Optional[str], data: Dict[str, Any], author: str = "") -> str:
    name = data.get("name", "").strip()
    if not name:
        raise StudioError("Hãy đặt tên cho mẫu.")
    existing = list_templates()
    if len(existing) >= MAX_TEMPLATES and not template_id:
        raise StudioError(f"Đã có {MAX_TEMPLATES} mẫu: xoá bớt mẫu cũ trước khi lưu mẫu mới.")

    tid = template_id if (template_id and _TEMPLATE_ID.match(template_id)) else uuid.uuid4().hex[:12]
    data["created_at"] = data.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data["author"] = author or data.get("author", "")
    _write_json(_templates_dir() / f"{tid}.json", data)
    return tid


def delete_template(template_id: str) -> None:
    f = _templates_dir() / f"{template_id}.json"
    if f.is_file():
        f.unlink()
