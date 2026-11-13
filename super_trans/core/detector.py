"""
Nhận diện ngôn ngữ tự động thông minh
"""

import re
import unicodedata
from typing import Tuple

VIETNAMESE_PATTERN = re.compile(
    r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
    r"ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]",
    re.IGNORECASE
)

# Các từ thông dụng đặc trưng tiếng Việt không dấu (để tăng độ chính xác)
VIETNAMESE_WORDS = {
    "va", "la", "cua", "trong", "cho", "voi", "khong", "nguoi", "duoc",
    "co", "mot", "nhung", "cac", "den", "nay", "ve", "se", "ra", "khi",
    "da", "tai", "tu", "nhu", "theo", "tren", "vao", "hon", "do", "ma"
}

def is_vietnamese(text: str) -> bool:
    """Kiểm tra xem văn bản có phải là tiếng Việt hay không."""
    if not text:
        return False

    norm_text = unicodedata.normalize("NFC", text)

    # 1. Kiểm tra dấu tiếng Việt
    if VIETNAMESE_PATTERN.search(norm_text):
        return True

    # 2. Kiểm tra từ phổ biến nếu văn bản không dấu
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if words:
        vi_word_count = sum(1 for w in words if w in VIETNAMESE_WORDS)
        if len(words) >= 3 and vi_word_count / len(words) > 0.4:
            return True

    return False

def resolve_languages(text: str, source_lang: str = None, target_lang: str = None,
                      primary_target: str = "vi", secondary_target: str = "en") -> Tuple[str, str]:
    """
    Xác định ngôn ngữ nguồn và đích.
    Nếu người dùng chỉ định thì dùng, nếu không thì tự động đảo chiều thông minh.
    """
    if source_lang and target_lang:
        return source_lang, target_lang

    if is_vietnamese(text):
        src = source_lang or "vi"
        tgt = target_lang or secondary_target
    else:
        src = source_lang or "auto"
        tgt = target_lang or primary_target

    return src, tgt
