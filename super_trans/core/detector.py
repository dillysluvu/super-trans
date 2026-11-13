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
    "đã", "tại", "từ", "như", "theo", "trên", "vào", "hơn", "đó", "mà"
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

    # 3. Phân tích các từ
    words = re.findall(r"\b[a-zA-Z\u00C0-\u024F\u1EA0-\u1EF9]+\b", norm.lower())
    clean_words = [re.sub(r"[^a-z]", "", w) for w in words]

    # Kiểm tra xem có phải câu tiếng Pháp không
    if any(w in FRENCH_WORDS for w in clean_words) and not any(w in VIETNAMESE_WORDS for w in words):
        return False

    # 4. Kiểm tra các ký tự thuần Việt
    if PURE_VI_PATTERN.search(norm):
        return True

    # 5. Kiểm tra các từ tiếng Việt thông dụng
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
    if source_lang and target_lang:
        return source_lang, target_lang

    if is_vietnamese(text):
        src = source_lang or "vi"
        tgt = target_lang or secondary_target
    else:
        # Tự động nhận diện nguồn (Anh, Pháp, Trung, ...) và dịch sang Tiếng Việt
        src = source_lang or "auto"
        tgt = target_lang or primary_target

    return src, tgt
