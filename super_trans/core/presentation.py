"""
Định dạng hiển thị tối giản cho SuperTrans.

Giao diện chính chỉ cần hai dòng:
    gốc : nghĩa
    engine · ngữ cảnh

Các hàm ở đây giữ nguyên nội dung quan trọng, cắt bớt phần thừa và loại bỏ
Markdown trước khi đưa lên Dynamic Island / toast / notification.
"""

import re

PAIR_SEPARATOR = " : "
DEFAULT_PAIR_LIMIT = 240
DEFAULT_CONTEXT_LIMIT = 140

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_EMPHASIS = re.compile(r"[*_`~]+")
_HTML_TAG = re.compile(r"<[^>]+>")
_RULE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_ANALYSIS_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:🔍\s*)?(?:Phân tích|Analysis)\b.*$"
)
_TRANSLATION_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:🌐\s*)?(?:Bản dịch|Translation)\b.*$"
)


def one_line(text: str) -> str:
    """Gộp mọi khoảng trắng/xuống dòng thành một dòng."""
    return " ".join((text or "").split())


def ellipsis(text: str, limit: int = DEFAULT_PAIR_LIMIT) -> str:
    """Cắt chuỗi theo giới hạn, thêm dấu … nếu cần."""
    text = one_line(text)
    limit = int(limit)
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def compact_pair(original: str, translated: str,
                 limit: int = DEFAULT_PAIR_LIMIT) -> str:
    """
    Tạo dòng ``gốc : nghĩa`` cân bằng độ dài.

    Ưu tiên giữ cả hai phía; phía ngắn sẽ nhường chỗ cho phía dài.
    """
    original = one_line(original)
    translated = one_line(translated)
    limit = max(16, int(limit))

    if not original:
        return ellipsis(translated, limit)
    if not translated:
        return ellipsis(original, limit)

    budget = max(2, limit - len(PAIR_SEPARATOR))
    original_cap = min(len(original), max(20, int(budget * 0.4)))
    original_short = ellipsis(original, original_cap)
    translated_cap = max(1, budget - len(original_short))
    translated_short = ellipsis(translated, translated_cap)

    # Nếu bản dịch ngắn, trả lại phần chỗ trống cho văn bản gốc.
    if len(translated_short) < translated_cap and len(original) > len(original_short):
        original_short = ellipsis(original, budget - len(translated_short))
        translated_short = ellipsis(
            translated, max(1, budget - len(original_short))
        )

    return ellipsis(
        f"{original_short}{PAIR_SEPARATOR}{translated_short}",
        limit,
    )


def _plain_markdown_line(line: str) -> str:
    """Bỏ ký hiệu Markdown khỏi một dòng nhưng giữ nội dung."""
    line = _HEADING.sub("", line or "")
    line = _BULLET.sub("", line)
    line = _MARKDOWN_LINK.sub(r"\1", line)
    line = _EMPHASIS.sub("", line)
    line = _HTML_TAG.sub("", line)
    return one_line(line)


def short_context(analysis: str,
                  limit: int = DEFAULT_CONTEXT_LIMIT) -> str:
    """
    Lấy một dòng ngữ cảnh ngắn từ phần phân tích Markdown của OpenCode.

    Không trả về tiêu đề hay nguyên khối phân tích; chỉ lấy dòng nội dung đầu
    tiên có nghĩa để đưa lên phụ đề Dynamic Island.
    """
    if not analysis:
        return ""

    text = (analysis or "").replace("\r\n", "\n")
    text = _CODE_FENCE.sub(" ", text)

    match = _ANALYSIS_HEADING.search(text)
    if match:
        text = text[match.end():]
    else:
        match = _TRANSLATION_HEADING.search(text)
        if match:
            text = text[match.end():]

    for raw_line in text.splitlines():
        raw_line = raw_line or ""
        if _RULE.match(raw_line):
            continue
        # Bỏ tiêu đề mục và dòng chỉ có chữ đậm, chỉ lấy nội dung thật.
        if raw_line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s*\*\*[^*]+\*\*\s*$", raw_line):
            continue
        line = _plain_markdown_line(raw_line)
        if not line or len(line) < 3:
            continue
        if line.startswith(("|", ">", "```")):
            continue
        return ellipsis(line, limit)

    return ""


def context_line(engine_name: str, context: str = "",
                 src_lang: str = "auto", tgt_lang: str = "vi",
                 limit: int = DEFAULT_PAIR_LIMIT) -> str:
    """
    Tạo phụ đề ``engine · ngữ cảnh``.

    Nếu chưa có ngữ cảnh, dùng hướng dịch thay thế để dòng phụ vẫn hữu ích.
    """
    engine = one_line(engine_name) or "SuperTrans"
    context = one_line(context)
    if context:
        line = f"{engine} · {context}"
    else:
        line = (
            f"{engine} · "
            f"{(src_lang or 'auto').upper()}→{(tgt_lang or 'vi').upper()}"
        )
    return ellipsis(line, limit)


