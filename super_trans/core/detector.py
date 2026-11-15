"""
Nhận diện ngôn ngữ tự động thông minh (Tối ưu cho Tiếng Anh, Pháp, Trung -> Tiếng Việt)
"""

import re
import unicodedata
from typing import Tuple

# 1. Ký tự chữ Hán / Tiếng Trung (CJK Unified Ideographs)
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")

# 2. Ký tự đặc trưng của tiếng Pháp (hoàn toàn không có trong tiếng Việt)
FRENCH_CHARS_PATTERN = re.compile(r"[çÇœŒæÆëËïÏüÜÿŸ]")

# 3. Các từ vựng mạo từ / liên từ / giới từ đặc trưng tiếng Pháp
FRENCH_WORDS = {
    "le", "la", "les", "des", "du", "de", "un", "une", "est", "sont", "cest",
    "vous", "nous", "ils", "elles", "avec", "pour", "dans", "sur", "aux",
    "mais", "donc", "merci", "bonjour", "bonsoir", "plait", "vie", "mon",
    "ton", "son", "notre", "votre", "leur", "cette", "cet", "ces", "bien", "cher"
}

# 4. Ký tự THUẦN VIỆT (Hoàn toàn không có trong tiếng Anh hay tiếng Pháp)
# Bao gồm: đ, Đ, ă, Ă, ơ, Ơ, ư, Ư và tất cả các ký tự có dấu hỏi, ngã, nặng, hoặc dấu kép tiếng Việt
PURE_VI_PATTERN = re.compile(
    r"[đĐăĂơƠưƯ"
    r"ảẢẻẺỉỈỏỎủỦỷỶ"
    r"ãÃẽẼĩĨõÕũŨỹỸ"
    r"ạẠẹẸịỊọỌụỤỵỴ"
    r"ấẤầẦẩẨẫẪậẬ"
    r"ắẮằẰẳẲẵẴặẶ"
    r"ếẾềỀểỂễỄệỆ"
    r"ốỐồỒổỔỗỖộỘ"
    r"ớỚờỜởỞỡỠợỢ"
    r"ứỨừỪửỬữỮựỰ]"
)

# 5. Các từ thông dụng đặc trưng tiếng Việt
VIETNAMESE_WORDS = {
    "và", "là", "của", "trong", "cho", "với", "không", "người", "được",
    "có", "một", "những", "các", "đến", "này", "về", "sẽ", "ra", "khi",
    "đã", "tại", "từ", "như", "theo", "trên", "vào", "hơn", "đó", "mà",
    "chào", "xin", "bạn", "tôi", "chúng", "họ", "cảm", "ơn", "hôm", "nay",
    "rất", "vui", "gặp", "lại", "nhé", "thế", "nào", "gì", "sao", "vì",
    "nếu", "thì", "để", "làm", "muốn", "cần", "phải", "nên", "thể", "đang",
}

def is_vietnamese(text: str) -> bool:
    """
    Kiểm tra xem văn bản có thực sự là tiếng Việt hay không.
    Phân biệt rõ ràng giữa Tiếng Việt và Tiếng Pháp (vốn có chung một số dấu như à, è, é, ê, ô, ù).
    """
    if not text:
        return False

    norm = unicodedata.normalize("NFC", text)

    # 1. Nếu có chữ Hán / Trung -> Chắc chắn không phải tiếng Việt
    if CHINESE_PATTERN.search(norm):
        return False

    # 2. Nếu có ký tự đặc trưng tiếng Pháp (ç, œ, ë, ï...) -> Chắc chắn không phải tiếng Việt
    if FRENCH_CHARS_PATTERN.search(norm):
        return False

    # 3. Tách từ để phân tích từ vựng
    words = re.findall(r"\b[a-zA-Z\u00C0-\u024F\u1EA0-\u1EF9]+\b", norm.lower())
    clean_words = [re.sub(r"[^a-z]", "", w) for w in words]

    # 4. Ký tự thuần Việt (ưu tiên trước khi xét từ vựng tiếng Pháp,
    #    tránh nhầm các câu như "Nó la mắng tôi" vì có từ "la")
    if PURE_VI_PATTERN.search(norm):
        return True

    # 5. Nếu có từ đặc trưng tiếng Pháp và không có từ tiếng Việt -> tiếng Pháp
    if any(w in FRENCH_WORDS for w in clean_words) and not any(w in VIETNAMESE_WORDS for w in words):
        return False

    # 6. Kiểm tra các từ tiếng Việt thông dụng
    if any(w in VIETNAMESE_WORDS for w in words):
        return True

    return False

def resolve_languages(text: str, source_lang: str = None, target_lang: str = None,
                      primary_target: str = "vi", secondary_target: str = "en") -> Tuple[str, str]:
    """
    Xác định ngôn ngữ nguồn và đích.
    Ưu tiên dịch sang Tiếng Việt (vi) cho mọi ngôn ngữ ngoại lai (Anh, Pháp, Trung...).
    Chỉ dịch sang Tiếng Anh nếu văn bản nguồn thực sự là Tiếng Việt.
    """
    # Người dùng chỉ định rõ ngôn ngữ nguồn
    if source_lang and source_lang != "auto":
        if target_lang:
            return source_lang, target_lang
        if source_lang == "vi":
            return "vi", secondary_target
        return source_lang, primary_target

    if is_vietnamese(text):
        return "vi", target_lang or secondary_target

    # Tự động nhận diện nguồn (Anh, Pháp, Trung, ...)
    return "auto", target_lang or primary_target
