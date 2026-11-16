import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from app.config import settings
from app.database import SessionLocal
from app.models import AiUsageLog, RawPost
from app.services.ai_key_router import resolve_candidates, record_key_usage, trip_circuit_breaker
from app.services.llm_providers import complete, LLMError

logger = logging.getLogger("inew.ai_copilot")


def _vn_day_start_utc() -> datetime:
    now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
    start_vn = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_vn - timedelta(hours=7)


def ai_usage_today(user_id: Optional[int] = None) -> Dict[str, int]:
    start = _vn_day_start_utc()
    db = SessionLocal()
    try:
        total = db.query(AiUsageLog).filter(AiUsageLog.created_at >= start).count()
        mine = 0
        if user_id:
            mine = (
                db.query(AiUsageLog)
                .filter(AiUsageLog.created_at >= start, AiUsageLog.user_id == user_id)
                .count()
            )
        return {"total": total, "mine": mine}
    finally:
        db.close()


def wrap_source(text: str, source_title: str) -> str:
    clean = re.sub(r"</?\s*nguon\s*>", "", text or "", flags=re.IGNORECASE)
    clean = clean[: settings.AI_MAX_INPUT_CHARS]
    header = f"<nguon>{source_title}</nguon>\n" if source_title else ""
    return f"{header}{clean}"


async def generate_title_summary(text: str, language: str = "vi") -> Dict[str, str]:
    """
    Generate a title and summary from source text using AI.
    Returns dict with 'title' and 'summary' keys.
    """
    lang_name_map = {
        "vi": "Tiếng Việt",
        "en": "English",
        "ko": "한국어 (Tiếng Hàn)",
        "ja": "日本語 (Tiếng Nhật)",
        "zh": "中文 (Tiếng Trung)",
        "th": "ไทย (Tiếng Thái)",
        "id": "Bahasa Indonesia"
    }
    lang_label = lang_name_map.get(language.lower(), "Tiếng Việt")

    system_prompt = f"""Bạn là chuyên gia biên tập báo chí. Hãy đọc nội dung tin tức sau và tạo:
1. TIÊU ĐỀ: Ngắn gọn, hấp dẫn, nắm bắt ý chính (tối đa 100 ký tự)
2. TÓM TẮT: 2-3 câu tóm gọn nội dung cốt lõi (tối đa 300 ký tự)

Ngôn ngữ đầu ra: {lang_label}
Định dạng JSON: {{"title": "...", "summary": "..."}}"""

    candidates = resolve_candidates()
    if not candidates:
        if settings.GEMINI_API_KEY:
            candidates.append({"key_id": 0, "provider": "gemini", "api_key": settings.GEMINI_API_KEY, "model": "gemini-1.5-flash"})
        elif settings.OPENAI_API_KEY:
            candidates.append({"key_id": 0, "provider": "openai", "api_key": settings.OPENAI_API_KEY, "model": "gpt-4o-mini"})

    if not candidates:
        return {"title": "Chưa cấu hình API key AI", "summary": "Vui lòng vào mục Cài đặt AI để thêm key (Google Gemini, OpenAI, Claude hoặc DeepSeek)."}

    cand = candidates[0]
    prompt_full = f"{system_prompt}\n\nNỘI DUNG NGUỒN:\n{text}"

    res = await complete(
        provider=cand["provider"],
        api_key=cand["api_key"],
        model=cand["model"],
        prompt=prompt_full,
        max_tokens=512
    )
    if cand.get("key_id"):
        record_key_usage(cand["key_id"], success=True)

    # Parse JSON response
    import json
    try:
        parsed = json.loads(res)
        return {"title": parsed.get("title", ""), "summary": parsed.get("summary", "")}
    except json.JSONDecodeError:
        # Fallback: try to extract title and summary from text response
        lines = res.strip().split("\n")
        title = lines[0].replace("TIÊU ĐỀ:", "").strip() if lines else ""
        summary = " ".join(lines[1:]).replace("TÓM TẮT:", "").strip() if len(lines) > 1 else ""
        return {"title": title[:100], "summary": summary[:300]}


async def post_text_for_ai(post_id: int) -> str:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return ""
        stitle = post.source_channel.title if post.source_channel else ""
        return wrap_source(post.article_text or post.edited_text or post.original_text or "", stitle)
    finally:
        db.close()


def get_length_instruction(script_length: str, custom_minutes: float = 1.0) -> str:
    if script_length == "shorts_60s":
        return (
            "- THỜI LƯỢNG MỤC TIÊU: Dưới 60 giây (tương đương 130 - 150 từ nói).\n"
            "- CẤU TRÚC BẮT BUỘC:\n"
            "  + HOOK (3 - 5 giây đầu): 1 câu mở đầu giật gân, trực diện, kích thích tò mò giữ chân người xem.\n"
            "  + THÂN BÀI (40 - 45 giây): Nhịp điệu dứt khoát, câu ngắn dưới 15 từ, tối ưu phát thanh, loại bỏ râu ria.\n"
            "  + KÊU GỌI HÀNH ĐỘNG (5 - 10 giây): Câu hỏi tranh luận hoặc kêu gọi đăng ký kênh."
        )
    elif script_length == "youtube_3_5m":
        return (
            "- THỜI LƯỢNG MỤC TIÊU: 3 đến 5 phút (khoảng 550 - 750 từ).\n"
            "- CẤU TRÚC BẮT BUỘC:\n"
            "  + Mở đầu hấp dẫn đặt vấn đề (30 giây).\n"
            "  + Thân bài chia thành 3 luận điểm sâu sắc có số liệu, dẫn chứng thực tế.\n"
            "  + Lời bình kết luận, dự báo xu hướng tương lai và câu hỏi mở cho khán giả."
        )
    elif script_length == "podcast_10_15m":
        return (
            "- THỜI LƯỢNG MỤC TIÊU: 10 đến 15 phút (khoảng 1500 - 2200 từ).\n"
            "- CẤU TRÚC BẮT BUỘC: Phong cách Podcast / Phát thanh trò chuyện chuyên sâu, mượt mà, sâu sắc, chia làm 5 phần:\n"
            "  1. Lời chào & Đặt vấn đề nóng hổi.\n"
            "  2. Bối cảnh nguồn cơn và dòng sự kiện.\n"
            "  3. Mổ xẻ bản chất đa chiều (Luận điểm 1, Luận điểm 2, Luận điểm 3).\n"
            "  4. Tác động kinh tế, xã hội và dự báo tương lai.\n"
            "  5. Thông điệp kết thúc và góc nhìn suy ngẫm."
        )
    else:
        mins = max(0.5, float(custom_minutes or 1.0))
        target_words = int(mins * 140)
        return (
            f"- THỜI LƯỢNG MỤC TIÊU: Khoảng {mins} phút (tương đương khoảng {target_words} từ nói, tốc độ ~140 từ/phút).\n"
            f"- CẤU TRÚC BẮT BUỘC: Phân bổ hợp lý tỷ lệ Mở bài (15%) - Thân bài chi tiết (70%) - Kết luận (15%), phù hợp phát thanh mượt mà."
        )


def get_headline_style_name(style_code: str) -> str:
    styles = {
        "sensational": "Giật gân thu hút, đánh mạnh vào cảm xúc và sự tò mò",
        "serious": "Thời sự nghiêm túc, chuẩn mực thông tấn chính thống",
        "curiosity": "Kích thích tò mò, mở ra bí mật hoặc câu hỏi chưa lời giải",
        "question": "Dạng câu hỏi trực diện thôi thúc người xem tìm câu trả lời",
        "seo": "Chuẩn SEO tối ưu tìm kiếm trên Google/YouTube, chứa từ khóa nóng"
    }
    return styles.get(style_code, "Hấp dẫn, thời sự và chuẩn xác")


async def generate_integrated_script(
    text: str,
    language: str = "vi",
    script_length: str = "shorts_60s",
    custom_minutes: float = 1.0,
    headline_style: str = "sensational",
    aspect_ratio: str = "9:16",
    user_id: Optional[int] = None
) -> str:
    """
    Sinh kịch bản phát thanh/video kết hợp 5W1H + Tháp Ngược + 4 Mức độ dài + 5 Kiểu Tít + Tỉ lệ khung hình.
    """
    lang_name_map = {
        "vi": "Tiếng Việt",
        "en": "English",
        "ko": "한국어 (Tiếng Hàn)",
        "ja": "日本語 (Tiếng Nhật)",
        "zh": "中文 (Tiếng Trung)",
        "th": "ไทย (Tiếng Thái)",
        "id": "Bahasa Indonesia"
    }
    lang_label = lang_name_map.get(language.lower(), "Tiếng Việt")
    length_instruction = get_length_instruction(script_length, custom_minutes)
    headline_instruction = get_headline_style_name(headline_style)

    system_prompt = f"""Bạn là Tổng biên tập và Chuyên gia biên kịch video/phát thanh hàng đầu.
Nhiệm vụ của bạn là chuyển hóa nội dung tin tức nguồn thành một KỊCH BẢN BIÊN TẬP HOÀN CHỈNH bằng ngôn ngữ: {lang_label}.

QUY TẮC CỐT LÕI BẮT BUỘC PHẢI KẾT HỢP:
1. 📑 BÓC TÁCH 5W1H:
   - Trích xuất nhanh 6 yếu tố cốt lõi: Who (Ai), What (Việc gì), Where (Ở đâu), When (Khi nào), Why (Tại sao), How (Thế nào).
2. ✍️ CẤU TRÚC MÔ HÌNH THÁP NGƯỢC (Inverted Pyramid):
   - Đưa ngay thông tin quan trọng nhất và diễn biến nóng hổi lên Sa-pô và đoạn mở đầu.
   - Các chi tiết bổ trợ, bối cảnh phụ nằm ở phía sau.
3. ⏱️ ĐỘ DÀI KỊCH BẢN:
{length_instruction}
4. 🏷️ TIÊU ĐỀ BÁO CHÍ:
   - Đề xuất 5 phương án tiêu đề khác nhau theo phong cách: {headline_instruction}.
5. 📐 ĐỊNH DẠNG KHUNG HÌNH MỤC TIÊU:
   - Khung hình: {aspect_ratio} (định hướng gợi ý bố cục trực quan phù hợp).

YÊU CẦU ĐỊNH DẠNG ĐẦU RA (Rõ ràng, chuyên nghiệp, dễ sử dụng):

# 🏷️ 5 GỢI Ý TIÊU ĐỀ ({headline_instruction})
1. [Tiêu đề 1]
2. [Tiêu đề 2]
3. [Tiêu đề 3]
4. [Tiêu đề 4]
5. [Tiêu đề 5]

---
# 📑 TỔNG HỢP 5W1H & SA-PÔ CỐT LÕI
- **Ai (Who):** ...
- **Việc gì (What):** ...
- **Ở đâu (Where):** ...
- **Khi nào (When):** ...
- **Tại sao (Why):** ...
- **Như thế nào (How):** ...
- **Sa-pô (Lead tháp ngược):** [Đoạn tóm tắt mở đầu gói gọn bản chất sự kiện]

---
# 🎙️ LỜI BÌNH KỊCH BẢN VOICE-OVER (SẴN SÀNG CHO PHÁT THANH / TTS)
[Toàn bộ lời bình đọc liên tục, câu ngắn gọn, không chứa ký tự lạ, viết rõ từ viết tắt như UBND thành Ủy ban nhân dân, TP.HCM thành Thành phố Hồ Chí Minh, viết rõ số thành chữ nếu cần để máy đọc mượt mà]

---
# 🔖 HASHTAGS ĐỀ XUẤT
#tintuc #thoisu ...
"""

    candidates = resolve_candidates()
    if not candidates:
        if settings.GEMINI_API_KEY:
            candidates.append({"key_id": 0, "provider": "gemini", "api_key": settings.GEMINI_API_KEY, "model": "gemini-1.5-flash"})
        elif settings.OPENAI_API_KEY:
            candidates.append({"key_id": 0, "provider": "openai", "api_key": settings.OPENAI_API_KEY, "model": "gpt-4o-mini"})

    if not candidates:
        return "Chưa cấu hình API key AI. Vui lòng vào mục Cài đặt AI để thêm key (Google Gemini, OpenAI, Claude hoặc DeepSeek)."

    cand = candidates[0]
    prompt_full = f"{system_prompt}\n\nNỘI DUNG NGUỒN CẦN XỬ LÝ:\n{text}"
    
    max_tokens = 4096 if script_length in ("podcast_10_15m", "custom") else 2048

    res = await complete(
        provider=cand["provider"],
        api_key=cand["api_key"],
        model=cand["model"],
        prompt=prompt_full,
        max_tokens=max_tokens
    )
    if cand.get("key_id"):
        record_key_usage(cand["key_id"], success=True)
    return res


async def analyze_script_scenes(
    script_text: str,
    aspect_ratio: str = "9:16",
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Phân tích kịch bản thành các phân cảnh trực quan (Scene Breakdown).
    Mỗi cảnh có prompt tiếng Anh để vẽ ảnh AI theo đúng tỷ lệ khung hình.
    """
    system_prompt = f"""Bạn là Đạo diễn hình ảnh và Giám đốc nghệ thuật (Art Director) chuyên nghiệp.
Hãy đọc kỹ kịch bản sau và phân tách thành danh sách 4 đến 8 phân cảnh hình ảnh minh họa trải dài theo mạch nội dung.

Tỉ lệ khung hình mục tiêu: {aspect_ratio}.

YÊU CẦU BẮT BUỘC:
Trả về ĐÚNG VÀ DUY NHẤT một mảng JSON nằm trong khối ```json ... ``` theo cấu trúc:
[
  {{
    "scene_id": 1,
    "timestamp_estimate": "00:00 - 00:08",
    "spoken_text": "Câu văn hoặc lời bình thoại trong phân cảnh này",
    "scene_description": "Mô tả ngắn gọn bằng tiếng Việt cảnh quay trực quan",
    "ai_prompt": "Detailed cinematic editorial photojournalism prompt in English, ultra-realistic, natural lighting, professional photography, 8k, aspect ratio {aspect_ratio}, no text, no watermark, no logo"
  }}
]
"""
    candidates = resolve_candidates()
    if not candidates:
        if settings.GEMINI_API_KEY:
            candidates.append({"key_id": 0, "provider": "gemini", "api_key": settings.GEMINI_API_KEY, "model": "gemini-1.5-flash"})
        elif settings.OPENAI_API_KEY:
            candidates.append({"key_id": 0, "provider": "openai", "api_key": settings.OPENAI_API_KEY, "model": "gpt-4o-mini"})

    if not candidates:
        return []

    cand = candidates[0]
    prompt_full = f"{system_prompt}\n\nKỊCH BẢN ĐẦU VÀO:\n{script_text}"

    raw = await complete(
        provider=cand["provider"],
        api_key=cand["api_key"],
        model=cand["model"],
        prompt=prompt_full,
        max_tokens=3000
    )

    if cand.get("key_id"):
        record_key_usage(cand["key_id"], success=True)

    # Extract JSON array
    try:
        match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", raw, re.IGNORECASE)
        if match:
            return json.loads(match.group(1))
        # Direct bracket matching
        match2 = re.search(r"(\[[\s\S]*?\])", raw)
        if match2:
            return json.loads(match2.group(1))
    except Exception as e:
        logger.warning(f"Failed to parse scenes JSON: {e}. Raw: {raw[:200]}")
    return []


async def run_ai_action(action: str, text: str, user_id: Optional[int] = None, **kwargs) -> str:
    """Xử lý các thao tác AI truyền thống hoặc mở rộng."""
    if action == "integrated_script":
        return await generate_integrated_script(
            text=text,
            language=kwargs.get("language", "vi"),
            script_length=kwargs.get("script_length", "shorts_60s"),
            custom_minutes=kwargs.get("custom_minutes", 1.0),
            headline_style=kwargs.get("headline_style", "sensational"),
            aspect_ratio=kwargs.get("aspect_ratio", "9:16"),
            user_id=user_id
        )

    prompts = {
        "translate": "Bạn là biên tập viên quốc tế chuyên nghiệp. Hãy dịch toàn bộ nội dung sau sang tiếng Việt chuẩn văn phong báo chí hiện đại, mượt mà và chính xác thuật ngữ:\n\n",
        "summarize": "Hãy tóm tắt ngắn gọn bài báo sau theo mô hình 5W1H (Who - What - Where - When - Why - How) thành các ý rõ ràng, súc tích:\n\n",
        "rewrite": "Hãy viết lại bài báo sau theo mô hình Tháp Ngược chuẩn báo chí (thông tin quan trọng nhất đặt lên đầu, tiếp theo là diễn biến chi tiết và bối cảnh phụ):\n\n",
        "headlines": "Hãy tạo 5 gợi ý tiêu đề (Headline) thật hấp dẫn, giật tít thu hút người đọc nhưng đúng sự thật, chuẩn SEO và văn phong báo chí cho bài sau:\n\n",
        "script": "Bạn là biên kịch video ngắn TikTok/Shorts/Reels. Hãy viết kịch bản voice-over dưới 60 giây (khoảng 130-150 từ) gồm Hook, Thân bài và Kêu gọi hành động (CTA) kèm hashtag từ bài sau:\n\n",
        "script_long": "Bạn là biên kịch video phân tích YouTube chuyên sâu (3 - 5 phút). Hãy viết kịch bản chi tiết gồm Mở đầu, 3 Luận điểm lớn có dẫn chứng, Lời bình kết từ bài sau:\n\n",
        "deep_dive_15min": "Bạn là chuyên gia phân tích bình luận thời sự và biên kịch Podcast/Radio hàng đầu. Hãy chuyển hóa nội dung bài viết sau thành một KỊCH BẢN PHÁT THANH / BÌNH LUẬN CHUYÊN SÂU có thời lượng khoảng 10-15 PHÚT (tương đương khoảng 1500-2200 từ, tốc độ đọc ~150-160 từ/phút).\n\nYÊU CẦU CẤU TRÚC CHI TIẾT:\n1. PHẦN 1: LỜI CHÀO & ĐẶT VẤN ĐỀ (Khoảng 1-2 phút): Hook gây ấn tượng, nêu bật vì sao sự kiện này quan trọng và đáng chú ý ngay lúc này.\n2. PHẦN 2: BỐI CẢNH LỊCH SỬ & NGUỒN CƠN (Khoảng 2-3 phút): Xâu chuỗi dòng sự kiện, diễn biến từ đầu dẫn tới tình huống hiện tại.\n3. PHẦN 3: PHÂN TÍCH ĐA CHIỀU & MỔ XẺ BẢN CHẤT (Khoảng 4-6 phút cho 10-15 phút dài):\n   - Luận điểm 1: Diễn biến cốt lõi, số liệu cụ thể và các phát ngôn chính thức.\n   - Luận điểm 2: Tác động trực tiếp đến đời sống, kinh tế, xã hội hoặc các bên liên quan.\n   - Luận điểm 3: Góc nhìn đối lập, rủi ro tiềm ẩn và các tranh luận chưa giải quyết.\n4. PHẦN 4: TÁC ĐỘNG KINH TẾ - XÃ HỘI & DỰ BÁO (Khoảng 2-3 phút): Phân tích lan tỏa, xu hướng dài hạn, kịch bản tốt/xấu.\n5. PHẦN 5: LỜI KẾT & GÓC NHÌN SUY NGÃM (Khoảng 1 phút): Tóm gọn thông điệp cốt lõi, để lại câu hỏi mở hoặc suy tư cho người nghe.\n\nPHONG CÁCH NGÔN NGỮ:\n- Chuyên nghiệp, sâu sắc, khách quan, có chiều sâu phân tích (không suồng sã, không chủ quan).\n- Dùng ngôn ngữ phát thanh tự nhiên: câu văn trôi chảy, ngắt nghỉ hợp lý, từ nối mượt mà cho TTS đọc.\n- Viết HOÀN TOÀN các từ viết tắt (VD: UBND -> Ủy ban nhân dân, TP.HCM -> Thành phố Hồ Chí Minh, km/h -> kilômét mỗi giờ, tr -> triệu, tỉ -> tỷ...).\n- Tránh lặp từ, tránh câu quá dài, ưu tiên câu chủ động.\n\nĐỊNH DẠNG XUẤT RA: Văn bản thuần túy, không markdown, không bullet point, các đoạn cách nhau bằng dòng trống để TTS hiểu ngắt đoạn.\n\nNội dung bài viết:\n\n",
        "social": "Hãy viết lại bài báo sau thành bài đăng Facebook/Telegram ngắn gọn, hấp dẫn kèm hashtag:\n\n",
        "polish_broadcast": "Bạn là chuyên gia phát thanh. Hãy biên tập lại đoạn văn sau sao cho tối ưu tuyệt đối cho giọng đọc AI (TTS) phát âm mượt mà: viết rõ toàn bộ từ viết tắt (UBND, TP.HCM, km/h, tr, tỉ...), ngắt câu tự nhiên có dấu câu hợp lý:\n\n"
    }
    prompt_prefix = prompts.get(action, "Phân tích bài viết sau:\n\n")

    candidates = resolve_candidates()
    if not candidates:
        if settings.GEMINI_API_KEY:
            candidates.append({"key_id": 0, "provider": "gemini", "api_key": settings.GEMINI_API_KEY, "model": "gemini-1.5-flash"})
        elif settings.OPENAI_API_KEY:
            candidates.append({"key_id": 0, "provider": "openai", "api_key": settings.OPENAI_API_KEY, "model": "gpt-4o-mini"})

    if not candidates:
        return "Chưa cấu hình API key AI. Vui lòng vào mục Cài đặt AI để thêm key."

    cand = candidates[0]
    res = await complete(
        provider=cand["provider"],
        api_key=cand["api_key"],
        model=cand["model"],
        prompt=f"{prompt_prefix}{text}",
        max_tokens=2048
    )
    if cand.get("key_id"):
        record_key_usage(cand["key_id"], success=True)
    return res
