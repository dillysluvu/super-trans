"""
Bộ máy dịch tốc độ cao (Fast Engine - Google GTX Endpoint)
Hoàn toàn miễn phí, không cần cấu hình API key, phản hồi ~100-200ms.

Hỗ trợ văn bản dài bằng cách chia nhỏ theo đoạn/câu để tránh giới hạn URL
của endpoint và giữ nguyên cấu trúc đoạn văn.
"""

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Tuple

from super_trans.core import native
from super_trans.engines.base import TranslationEngine

MAX_CHUNK_CHARS = 1800
REQUEST_TIMEOUT = 8
MAX_ATTEMPTS = 2


class FastEngine(TranslationEngine):
    name: str = "Fast (Google)"

    @staticmethod
    def split_text(text: str, limit: int = MAX_CHUNK_CHARS) -> List[str]:
        """
        Chia văn bản thành các đoạn <= limit ký tự.
        Ưu tiên cắt tại xuống dòng, sau đó tới cuối câu, cuối cùng mới cắt cứng.
        """
        text = text.strip()
        if not text:
            return []
        if len(text) <= limit:
            return [text]

        # Văn bản dài: thử helper Rust trước, fallback thuần Python bên dưới.
        native_chunks = native.split_text(text, limit)
        if native_chunks:
            return native_chunks

        chunks: List[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining.strip())
                break

            window = remaining[:limit]

            # 1. Ưu tiên xuống dòng (giữ ranh giới đoạn văn)
            cut = window.rfind("\n")
            if cut < limit // 2:
                # 2. Cắt tại cuối câu
                sentence_ends = list(re.finditer(r"[.!?。！？](?:\s|$)", window))
                cut = sentence_ends[-1].end() if sentence_ends else -1
            if cut < limit // 2:
                # 3. Cắt tại khoảng trắng gần nhất
                cut = window.rfind(" ")
            if cut < limit // 2:
                # 4. Cắt cứng (văn bản không có khoảng trắng, ví dụ tiếng Trung)
                cut = limit

            chunk = remaining[:cut].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[cut:].lstrip()

        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _parse_response(data, fallback_src: str) -> Tuple[str, str]:
        """Trích xuất bản dịch và ngôn ngữ nguồn từ JSON của Google GTX."""
        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            raise RuntimeError("Phản hồi từ bộ máy dịch không hợp lệ.")

        parts = []
        for sentence in data[0]:
            if isinstance(sentence, list) and sentence and sentence[0]:
                parts.append(str(sentence[0]))

        translated = unicodedata.normalize("NFC", "".join(parts).strip())
        detected_src = data[2] if len(data) > 2 and isinstance(data[2], str) else fallback_src
        return translated, detected_src

    def _request_chunk(self, text: str, src_lang: str, tgt_lang: str):
        body = urllib.parse.urlencode({
            "client": "gtx",
            "sl": src_lang,
            "tl": tgt_lang,
            "dt": "t",
            "q": text,
        }).encode("utf-8")
        url = "https://translate.googleapis.com/translate_a/single"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
        )

        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_error = exc
                if attempt + 1 < MAX_ATTEMPTS:
                    time.sleep(0.3)

        raise RuntimeError(f"Lỗi kết nối bộ máy dịch FastEngine: {last_error}")

    def translate(self, text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Tuple[str, str]:
        if not text or not text.strip():
            return "", src_lang

        chunks = self.split_text(text.strip())
        translated_parts: List[str] = []
        detected_src = src_lang

        for index, chunk in enumerate(chunks):
            data = self._request_chunk(chunk, src_lang, tgt_lang)
            translated, chunk_src = self._parse_response(data, src_lang)
            if index == 0 and chunk_src:
                detected_src = chunk_src
            if translated:
                translated_parts.append(translated)

        result = "\n".join(translated_parts).strip()
        if not result:
            raise RuntimeError("Bộ máy dịch không trả về nội dung.")
        return result, detected_src
