"""
Cầu nối tới helper Rust tùy chọn (``super-trans-native``).

Helper chỉ xử lý phần chia văn bản dài — phần tốn CPU khi dịch tài liệu lớn.
Nếu chưa build Rust hoặc helper gặp lỗi, mọi thứ tự động quay về thuần Python.
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional

NATIVE_NAME = "super-trans-native"
MIN_NATIVE_CHARS = 4000

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CANDIDATES = (
    os.path.expanduser("~/.local/lib/super-trans/" + NATIVE_NAME),
    os.path.join(PROJECT_ROOT, "native", "target", "release", NATIVE_NAME),
    os.path.join(PROJECT_ROOT, "native", "target", "debug", NATIVE_NAME),
)


def find_binary() -> Optional[str]:
    """Tìm helper Rust theo thứ tự: biến môi trường, cài đặt, build tại chỗ, PATH."""
    override = os.environ.get("SUPERTRANS_NATIVE_BIN")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return override

    for candidate in _CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return shutil.which(NATIVE_NAME)


def available() -> bool:
    return find_binary() is not None


def version() -> str:
    binary = find_binary()
    if not binary:
        return ""
    try:
        res = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def split_text(text: str, limit: int) -> Optional[List[str]]:
    """
    Chia văn bản bằng helper Rust. Trả về None để Python tự xử lý nếu:
      - văn bản ngắn (không đáng để khởi tạo tiến trình),
      - helper chưa được build,
      - helper lỗi hoặc kết quả không khớp nội dung gốc.
    """
    if not text or len(text) < MIN_NATIVE_CHARS:
        return None
    if "\x00" in text:
        return None

    binary = find_binary()
    if not binary:
        return None

    try:
        res = subprocess.run(
            [binary, "chunk", "--limit", str(int(limit))],
            input=text,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

    if res.returncode != 0 or not res.stdout:
        return None

    chunks = [chunk.strip() for chunk in res.stdout.split("\x00") if chunk.strip()]
    if not chunks:
        return None
    if any(len(chunk) > limit for chunk in chunks):
        return None

    # Kiểm tra không mất nội dung (bỏ qua khoảng trắng tại ranh giới).
    if "".join(text.split()) != "".join("".join(chunks).split()):
        return None

    return chunks


def status() -> Dict[str, object]:
    """Thông tin cho lệnh --doctor."""
    binary = find_binary()
    return {
        "available": bool(binary),
        "path": binary or "",
        "version": version(),
        "threshold": MIN_NATIVE_CHARS,
    }
