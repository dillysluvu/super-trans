"""
Lớp cơ sở (Base Class) cho các bộ máy dịch thuật
"""

from abc import ABC, abstractmethod
from typing import Tuple

class TranslationEngine(ABC):
    name: str = "BaseEngine"

    @abstractmethod
    def translate(self, text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Tuple[str, str]:
        """
        Dịch văn bản từ src_lang sang tgt_lang.
        Trả về: (translated_text, detected_source_language)
        """
        pass
