"""Batch importing and bulk ingestion of news channels."""

from typing import List, Dict, Any
from app.database import SessionLocal
from app.models import SourceChannel, _utcnow


def import_telegram_channels(channel_list: List[Dict[str, Any]]) -> int:
    db = SessionLocal()
    imported = 0
    try:
        for item in channel_list:
            cid = item.get("id") or item.get("telegram_channel_id")
            title = item.get("title") or item.get("name") or str(cid)
            if not cid:
                continue
            exist = db.query(SourceChannel).filter(SourceChannel.telegram_channel_id == cid).first()
            if not exist:
                src = SourceChannel(
                    title=title,
                    source_type="telegram",
                    telegram_channel_id=cid,
                    url=item.get("url", ""),
                    created_at=_utcnow()
                )
                db.add(src)
                imported += 1
        db.commit()
    finally:
        db.close()
    return imported
