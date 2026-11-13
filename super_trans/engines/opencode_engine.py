"""
Bộ máy dịch thông minh AI tích hợp trực tiếp OpenCode (OpenCode AI Engine)
Tận dụng sức mạnh LLM (DeepSeek, GLM, Nemotron) để dịch theo ngữ cảnh,
phân tích thành ngữ, tiếng lóng kỹ thuật và ngữ pháp.
"""

import subprocess
import shutil
import os
import re
from typing import Tuple
from super_trans.engines.base import TranslationEngine

class OpenCodeEngine(TranslationEngine):
    name: str = "OpenCode AI"

    def __init__(self, model: str = "opencode/deepseek-v4.1-flash-free",
                 opencode_bin: str = None):
        self.model = model
        self.bin_path = opencode_bin or self._find_opencode()

    def _find_opencode(self) -> str:
        """Tìm đường dẫn thực thi của OpenCode."""
        custom_path = os.path.expanduser("~/.opencode/bin/opencode")
        if os.path.exists(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        which_path = shutil.which("opencode")
        if which_path:
            return which_path
        return "opencode"

    def translate(self, text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Tuple[str, str]:
        if not text or not text.strip():
            return "", src_lang

        target_desc = "Tiếng Việt" if tgt_lang == "vi" else "English" if tgt_lang == "en" else tgt_lang

        prompt = (
            f"Bạn là chuyên gia dịch thuật và phân tích ngôn ngữ hàng đầu.\n"
            f"Nhiệm vụ: Dịch văn bản sau sang {target_desc}.\n"
            f"- Đưa ra bản dịch tự nhiên, chuẩn xác nhất theo ngữ cảnh.\n"
            f"- Nếu văn bản có thành ngữ, tiếng lóng, từ đồng nghĩa hoặc thuật ngữ kỹ thuật, "
            f"hãy thêm mục phân tích ngắn gọn, súc tích.\n"
            f"- Định dạng rõ ràng, đẹp mắt.\n\n"
            f"Văn bản cần dịch:\n\"\"\"{text.strip()}\"\"\""
        )

        cmd = [
            self.bin_path,
            "run",
            "--auto",
            "--standalone",
            "-m", self.model,
            prompt
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if res.returncode != 0:
                err_msg = res.stderr.strip() or f"Thoát với mã {res.returncode}"
                raise RuntimeError(f"OpenCode trả về lỗi: {err_msg}")

            output = res.stdout.strip()
            # Làm sạch các dòng log hệ thống như '> build · ...'
            lines = output.split("\n")
            cleaned_lines = [
                line for line in lines
                if not line.startswith("> build")
                and not line.startswith("> run")
                and not line.startswith("$ ")
            ]
            cleaned_result = "\n".join(cleaned_lines).strip()
            return cleaned_result, src_lang
        except subprocess.TimeoutExpired:
            raise RuntimeError("Quá thời gian phản hồi từ OpenCode AI (timeout > 25s).")
        except Exception as e:
            raise RuntimeError(f"Lỗi khi gọi OpenCode AI: {e}")
