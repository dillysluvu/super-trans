"""
Bộ máy dịch thông minh AI tích hợp trực tiếp OpenCode (OpenCode AI Engine)
Tận dụng sức mạnh LLM (DeepSeek, GLM, Nemotron) để dịch theo ngữ cảnh,
phân tích thành ngữ, tiếng lóng kỹ thuật và ngữ pháp.
"""

import os
import re
import shutil
import subprocess
from typing import Tuple

from super_trans.engines.base import TranslationEngine

DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TRANSLATION_BLOCK = re.compile(
    r"<<<\s*TRANSLATION\s*>>>\s*(.*?)\s*<<<\s*ANALYSIS\s*>>>\s*(.*)",
    re.IGNORECASE | re.DOTALL,
)


class OpenCodeEngine(TranslationEngine):
    name: str = "OpenCode AI"

    def __init__(self, model: str = DEFAULT_MODEL,
                 opencode_bin: str = None, timeout: float = 120.0):
        self.model = model or DEFAULT_MODEL
        self.bin_path = opencode_bin or self._find_opencode()
        self.timeout = float(timeout)

    def _find_opencode(self) -> str:
        """Tìm đường dẫn thực thi của OpenCode."""
        custom_path = os.path.expanduser("~/.opencode/bin/opencode")
        if os.path.exists(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        which_path = shutil.which("opencode")
        if which_path:
            return which_path
        return "opencode"

    @staticmethod
    def _clean_output(output: str) -> str:
        """Loại bỏ mã màu ANSI, log khởi động và code fence bao ngoài."""
        output = ANSI_ESCAPE.sub("", output or "")
        lines = [
            line for line in output.splitlines()
            if not line.startswith(("> build", "> run"))
        ]
        cleaned = "\n".join(lines).strip()

        if cleaned.startswith("```"):
            fence_lines = cleaned.splitlines()
            if fence_lines and fence_lines[0].startswith("```"):
                fence_lines = fence_lines[1:]
            if fence_lines and fence_lines[-1].strip() == "```":
                fence_lines = fence_lines[:-1]
            cleaned = "\n".join(fence_lines).strip()

        return cleaned

    def _run_prompt(self, prompt: str) -> str:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"

        cmd = [
            self.bin_path,
            "run",
            "--auto",
            "--standalone",
            "-m", self.model,
            prompt,
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Không tìm thấy OpenCode CLI. Cài đặt OpenCode hoặc chọn engine 'fast'."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Quá thời gian phản hồi từ OpenCode AI (timeout {self.timeout:.0f}s)."
            ) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Lỗi khi gọi OpenCode AI: {exc}") from exc

        if res.returncode != 0:
            err_msg = (res.stderr or res.stdout or "").strip()
            raise RuntimeError(f"OpenCode trả về lỗi: {err_msg or f'mã {res.returncode}'}")

        cleaned = self._clean_output(res.stdout)
        if not cleaned:
            raise RuntimeError("OpenCode AI không trả về nội dung.")
        return cleaned

    @staticmethod
    def _target_name(tgt_lang: str) -> str:
        return {"vi": "Tiếng Việt", "en": "English"}.get(tgt_lang, tgt_lang)

    def translate(self, text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Tuple[str, str]:
        """Dịch sạch (không kèm phân tích) — phù hợp để dán/thay thế tại chỗ."""
        if not text or not text.strip():
            return "", src_lang

        prompt = (
            "Bạn là chuyên gia dịch thuật hàng đầu.\n"
            f"Hãy dịch văn bản dưới đây sang {self._target_name(tgt_lang)}.\n"
            "- Giữ nguyên ý nghĩa, sắc thái và định dạng đoạn.\n"
            "- Không thêm lời giải thích, không thêm tiêu đề, không dùng code fence.\n"
            "- Chỉ trả về duy nhất bản dịch.\n\n"
            "Văn bản cần dịch:\n"
            f'"""{text.strip()}"""'
        )
        return self._run_prompt(prompt), src_lang

    def analyze(self, text: str, src_lang: str = "auto",
                tgt_lang: str = "vi") -> Tuple[str, str, str]:
        """
        Dịch + phân tích chuyên sâu.
        Trả về: (bản dịch sạch, markdown phân tích đầy đủ, ngôn ngữ nguồn)
        """
        if not text or not text.strip():
            return "", "", src_lang

        target = self._target_name(tgt_lang)
        prompt = (
            "Bạn là chuyên gia dịch thuật và phân tích ngôn ngữ hàng đầu.\n"
            f"Nhiệm vụ: dịch văn bản sau sang {target}, sau đó phân tích ngữ cảnh.\n\n"
            "YÊU CẦU ĐỊNH DẠNG (bắt buộc tuân thủ đúng hai mốc):\n"
            "<<<TRANSLATION>>>\n"
            "(chỉ đặt bản dịch sạch ở đây)\n"
            "<<<ANALYSIS>>>\n"
            "(phân tích bằng Markdown: thành ngữ/điển tích, sắc thái, ngữ pháp, "
            "từ khó và gợi ý cách dùng)\n\n"
            "Văn bản cần xử lý:\n"
            f'"""{text.strip()}"""'
        )

        output = self._run_prompt(prompt)
        match = TRANSLATION_BLOCK.search(output)

        if match:
            translation = match.group(1).strip()
            analysis_body = match.group(2).strip()
            if not translation:
                translation = analysis_body or output
            analysis = (
                f"## 🌐 Bản dịch\n\n{translation}\n\n"
                f"## 🔍 Phân tích\n\n{analysis_body}"
            )
        else:
            # LLM không tuân thủ mốc: dùng toàn bộ output làm bản dịch/phân tích
            translation = output
            analysis = output

        return translation, analysis, src_lang
