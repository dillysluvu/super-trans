"""
Bộ máy dịch tốc độ cao (Fast Engine - Google GTX Endpoint)
Hoàn toàn miễn phí, không cần cấu hình API key, phản hồi ~100-200ms.
"""

import urllib.request
import urllib.parse
import json
import unicodedata
from typing import Tuple
from super_trans.engines.base import TranslationEngine

class FastEngine(TranslationEngine):
    name: str = "Fast (Google)"

    def translate(self, text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Tuple[str, str]:
        if not text or not text.strip():
            return "", src_lang

        encoded_q = urllib.parse.quote(text.strip())
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={src_lang}&tl={tgt_lang}&dt=t&q={encoded_q}"
        )

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read().decode("utf-8")
                data = json.loads(content)

                # data[0] chứa các mảng câu đã dịch
                parts = []
                for sentence in data[0]:
                    if sentence and len(sentence) > 0 and sentence[0]:
                        parts.append(sentence[0])

                translated = unicodedata.normalize("NFC", "".join(parts).strip())
                detected_src = data[2] if len(data) > 2 and data[2] else src_lang
                return translated, detected_src
        except Exception as e:
            raise RuntimeError(f"Lỗi kết nối bộ máy dịch FastEngine: {e}")
