import os
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from app.config import settings
from app.database import SessionLocal
from app.models import RawPost, MediaItem, MediaType, AiUsageLog
from app.services.tasks import spawn

logger = logging.getLogger("ak_news.ai_media")

MEDIA_AI_ACTIONS = {
    "image_describe": {
        "title": "🖼️ Mô tả & đọc chữ",
        "media_type": MediaType.PHOTO,
        "system": (
            "Bạn là biên tập viên ảnh của một tòa soạn Việt Nam.\n"
            "Xem ảnh và trả lời bằng tiếng Việt theo đúng mẫu:\n"
            "MÔ TẢ: (2-3 câu mô tả bối cảnh, sự kiện, con người, hành động chính)\n"
            "CHỮ TRONG ẢNH: (liệt kê toàn bộ chữ, con số, bảng hiệu, biển số xe... nếu có, hoặc ghi 'Không có')\n"
            "CHI TIẾT ĐÁNG CHÚ Ý: (trang phục, địa danh, cờ, vũ khí, logo, thời tiết...)\n"
            "CHÚ THÍCH ĐỀ XUẤT: (1 câu chú thích ảnh chuẩn văn phong báo chí)\n"
        )
    },
    "image_verify": {
        "title": "🔎 Gợi ý kiểm chứng ảnh",
        "media_type": MediaType.PHOTO,
        "system": (
            "Bạn là chuyên viên kiểm chứng hình ảnh (OSINT) hỗ trợ phóng viên.\n"
            "Đưa ra các gợi ý để PHÓNG VIÊN tự kiểm tra tính xác thực của ảnh:\n"
            "1. DẤU HIỆU CẮT GHÉP / AI: (bóng đổ, ánh sáng bất thường, bàn tay, chi tiết phi lý)\n"
            "2. ĐỊA DANH & THỜI ĐIỂM: (biển báo, kiến trúc, thời tiết có khớp nguồn tin không)\n"
            "3. TỪ KHÓA TÌM KIẾM ẢNH NGƯỢC: (3-5 cụm từ tiếng Việt/Anh để tra cứu nguồn gốc)\n"
            "4. ĐÁNH GIÁ MỨC ĐỘ TIN CẬY: (Cao / Cần thận trọng / Nghi vấn)\n"
        )
    },
    "video_summary": {
        "title": "🎞️ Tóm tắt theo mốc",
        "media_type": MediaType.VIDEO,
        "system": (
            "Bạn là biên tập viên video thời sự.\n"
            "Xem toàn bộ video và trả lời bằng tiếng Việt:\n"
            "TÓM TẮT: (2-3 câu khái quát nội dung video)\n"
            "CÁC MỐC THỜI GIAN CHÍNH:\n"
            "- [00:00]: Mô tả ngắn\n"
            "- [00:xx]: Mô tả ngắn\n"
            "ĐÁNH GIÁ: (chất lượng hình ảnh, âm thanh, tính thời sự)\n"
        )
    },
    "video_transcript": {
        "title": "🗣️ Chép lời + dịch",
        "media_type": MediaType.VIDEO,
        "system": (
            "Bạn là biên dịch viên phụ đề chuyên nghiệp.\n"
            "Chép lại toàn bộ lời nói và chữ quan trọng trên màn hình trong video.\n"
            "Nếu có tiếng nước ngoài, hãy dịch sang tiếng Việt chuẩn xác.\n"
            "Trình bày rõ ràng theo mốc thời gian [phút:giây].\n"
        )
    },
    "video_subtitles": {
        "title": "💬 Phụ đề tiếng Việt (SRT)",
        "media_type": MediaType.VIDEO,
        "system": (
            "Bạn là biên tập viên phụ đề truyền hình.\n"
            "Tạo phụ đề TIẾNG VIỆT cho video ở định dạng SRT chuẩn, khớp mốc thời gian.\n"
            "Mỗi dòng phụ đề không quá 18-20 ký tự, ngắt nhịp tự nhiên dễ đọc trên màn hình dọc.\n"
            "Chỉ xuất nội dung định dạng .srt hợp lệ.\n"
        )
    },
    "video_highlights": {
        "title": "✂️ Gợi ý đoạn cắt Shorts",
        "media_type": MediaType.VIDEO,
        "system": (
            "Bạn là biên kịch video ngắn (Shorts/Reels/TikTok).\n"
            "Đề xuất tối đa 3 đoạn cắt hay nhất để làm video ngắn dưới 60 giây:\n"
            "ĐOẠN 1: [Từ giây -> Đến giây] - Lý do chọn, Tiêu đề giật tít đề xuất\n"
            "ĐOẠN 2: [Từ giây -> Đến giây] - Lý do chọn, Tiêu đề giật tít đề xuất\n"
            "ĐOẠN 3: [Từ giây -> Đến giây] - Lý do chọn, Tiêu đề giật tít đề xuất\n"
        )
    }
}
