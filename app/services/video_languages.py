from typing import Dict, List, Optional, Any

DEFAULT_LANGUAGE = "vi"

LANGUAGES: Dict[str, Dict[str, Any]] = {
    "vi": {
        "name": "Tiếng Việt",
        "code": "vi",
        "default_voice": "vi-VN-HoaiMyNeural",
        "voices": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My (Nữ)", "gender": "Female"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh (Nam)", "gender": "Male"},
        ],
        "newsroom_header": "TIN NÓNG ĐA NỀN TẢNG",
        "newsroom_footer": "Nhấn theo dõi để không bỏ lỡ tin tức mới nhất!",
    },
    "en": {
        "name": "English",
        "code": "en",
        "default_voice": "en-US-AvaNeural",
        "voices": [
            {"id": "en-US-AvaNeural", "name": "Ava (Female)", "gender": "Female"},
            {"id": "en-US-AndrewNeural", "name": "Andrew (Male)", "gender": "Male"},
            {"id": "en-US-EmmaNeural", "name": "Emma (Female)", "gender": "Female"},
            {"id": "en-US-BrianNeural", "name": "Brian (Male)", "gender": "Male"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia (UK Female)", "gender": "Female"},
            {"id": "en-GB-RyanNeural", "name": "Ryan (UK Male)", "gender": "Male"},
        ],
        "newsroom_header": "BREAKING NEWS MULTI-PLATFORM",
        "newsroom_footer": "Follow to stay updated with the latest news!",
    },
    "ko": {
        "name": "한국어",
        "code": "ko",
        "default_voice": "ko-KR-SunHiNeural",
        "voices": [
            {"id": "ko-KR-SunHiNeural", "name": "SunHi (Female)", "gender": "Female"},
            {"id": "ko-KR-InJoonNeural", "name": "InJoon (Male)", "gender": "Male"},
        ],
        "newsroom_header": "속보 멀티 플랫폼",
        "newsroom_footer": "최신 뉴스를 놓치지 않으려면 팔로우하세요!",
    },
    "ja": {
        "name": "日本語",
        "code": "ja",
        "default_voice": "ja-JP-NanamiNeural",
        "voices": [
            {"id": "ja-JP-NanamiNeural", "name": "Nanami (Female)", "gender": "Female"},
            {"id": "ja-JP-KeitaNeural", "name": "Keita (Male)", "gender": "Male"},
        ],
        "newsroom_header": "マルチプラットフォーム速報",
        "newsroom_footer": "最新ニュースをお見逃しなく！フォローしてください",
    },
    "zh": {
        "name": "中文",
        "code": "zh",
        "default_voice": "zh-CN-XiaoxiaoNeural",
        "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (女声)", "gender": "Female"},
            {"id": "zh-CN-YunxiNeural", "name": "云希 (男声)", "gender": "Male"},
            {"id": "zh-CN-YunyangNeural", "name": "云扬 (专业新闻)", "gender": "Male"},
        ],
        "newsroom_header": "全平台即时快讯",
        "newsroom_footer": "关注我们，随时掌握最新资讯！",
    },
    "th": {
        "name": "ไทย",
        "code": "th",
        "default_voice": "th-TH-PremwadeeNeural",
        "voices": [
            {"id": "th-TH-PremwadeeNeural", "name": "Premwadee (Female)", "gender": "Female"},
            {"id": "th-TH-NiwatNeural", "name": "Niwat (Male)", "gender": "Male"},
        ],
        "newsroom_header": "ข่าวเด่น มัลติแพลตฟอร์ม",
        "newsroom_footer": "กดติดตามเพื่อไม่ให้พลาดข่าวสารล่าสุด!",
    },
    "id": {
        "name": "Bahasa Indonesia",
        "code": "id",
        "default_voice": "id-ID-GadisNeural",
        "voices": [
            {"id": "id-ID-GadisNeural", "name": "Gadis (Female)", "gender": "Female"},
            {"id": "id-ID-ArdiNeural", "name": "Ardi (Male)", "gender": "Male"},
        ],
        "newsroom_header": "BERITA MULTI-PLATFORM",
        "newsroom_footer": "Ikuti agar tidak ketinggalan berita terbaru!",
    },
}

def default_voice_for(lang: str = "vi") -> str:
    lang_info = LANGUAGES.get(lang.lower(), LANGUAGES[DEFAULT_LANGUAGE])
    return lang_info["default_voice"]

def newsroom_default(lang: str = "vi") -> Dict[str, str]:
    lang_info = LANGUAGES.get(lang.lower(), LANGUAGES[DEFAULT_LANGUAGE])
    return {
        "header": lang_info["newsroom_header"],
        "footer": lang_info["newsroom_footer"],
    }

def edge_voices(lang: Optional[str] = None) -> List[Dict[str, Any]]:
    if lang and lang in LANGUAGES:
        return LANGUAGES[lang]["voices"]
    result = []
    for l_key, l_val in LANGUAGES.items():
        for v in l_val["voices"]:
            result.append({**v, "lang": l_key})
    return result

def language_of_voice(voice_key: str) -> str:
    for l_code, l_info in LANGUAGES.items():
        for v in l_info["voices"]:
            if v["id"].lower() == voice_key.lower():
                return l_code
    return DEFAULT_LANGUAGE

def choices() -> List[Dict[str, Any]]:
    return [
        {"code": code, "label": info["name"], "voice": info["default_voice"]}
        for code, info in LANGUAGES.items()
    ]
