"""
Tương tác Clipboard & Selection trên Wayland / X11.

Điểm quan trọng: PRIMARY selection (vùng đang bôi đen) và CLIPBOARD (Ctrl+C)
là hai nguồn khác nhau. Khi thay thế tại chỗ, SuperTrans chỉ chấp nhận PRIMARY
để tránh dán đè bằng một nội dung clipboard cũ không liên quan.
"""

import shutil
import subprocess
from dataclasses import dataclass

from super_trans.core import dms

# Nguồn văn bản được chọn
SOURCE_PRIMARY = "primary"
SOURCE_CLIPBOARD = "clipboard"
SOURCE_NONE = ""


@dataclass(frozen=True)
class Selection:
    """Kết quả đọc vùng chọn, kèm nguồn gốc."""
    text: str
    source: str = SOURCE_NONE

    def __bool__(self) -> bool:
        return bool(self.text)


def _run_text(cmd, timeout: float = 1.0) -> str:
    """Chạy lệnh đọc văn bản, trả về chuỗi rỗng nếu lỗi/không có dữ liệu."""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return ""
    if res.returncode != 0:
        return ""
    return (res.stdout or "").strip()


def get_primary_selection() -> str:
    """Đọc vùng đang bôi đen (PRIMARY), không fallback sang clipboard."""
    if shutil.which("wl-paste"):
        text = _run_text(["wl-paste", "--primary", "--no-newline"])
        if text:
            return text

    if shutil.which("xclip"):
        text = _run_text(["xclip", "-o", "-selection", "primary"])
        if text:
            return text

    return ""


def get_clipboard_text() -> str:
    """Đọc nội dung clipboard thông thường (Ctrl+C)."""
    if shutil.which("wl-paste"):
        text = _run_text(["wl-paste", "--no-newline"])
        if text:
            return text

    if shutil.which("xclip"):
        text = _run_text(["xclip", "-o", "-selection", "clipboard"])
        if text:
            return text

    return ""


def get_selection(prefer_clipboard: bool = True) -> Selection:
    """
    Đọc vùng chọn và cho biết nguồn.

    - Luôn ưu tiên PRIMARY (vùng đang bôi đen).
    - Chỉ fallback sang CLIPBOARD khi ``prefer_clipboard=True``.
    - ``--replace`` nên đặt ``prefer_clipboard=False`` để tránh dán nhầm.
    """
    primary = get_primary_selection()
    if primary:
        return Selection(primary, SOURCE_PRIMARY)

    if prefer_clipboard:
        clipboard = get_clipboard_text()
        if clipboard:
            return Selection(clipboard, SOURCE_CLIPBOARD)

    return Selection("", SOURCE_NONE)


def get_selection_text(prefer_clipboard: bool = True) -> str:
    """Tương thích ngược: chỉ trả về chuỗi văn bản đang chọn."""
    return get_selection(prefer_clipboard=prefer_clipboard).text


def set_clipboard_text(text: str) -> bool:
    """Sao chép văn bản vào clipboard hệ thống (ưu tiên DMS Clipboard)."""
    if not text:
        return False

    # 1. DMS Clipboard Manager: đồng bộ trực tiếp với lịch sử clipboard của DMS
    if dms.copy_text(text):
        return True

    if shutil.which("wl-copy"):
        try:
            proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=2)
            return proc.returncode == 0
        except Exception:
            pass

    if shutil.which("xclip"):
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text, timeout=2)
            return proc.returncode == 0
        except Exception:
            pass

    return False


def set_primary_text(text: str) -> bool:
    """Đưa văn bản vào PRIMARY selection (hỗ trợ middle-click)."""
    if not text:
        return False

    if shutil.which("wl-copy"):
        try:
            proc = subprocess.Popen(
                ["wl-copy", "--primary"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text, timeout=2)
            if proc.returncode == 0:
                return True
        except Exception:
            pass

    if shutil.which("xclip"):
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "primary"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text, timeout=2)
            return proc.returncode == 0
        except Exception:
            pass

    return False


def selection_available() -> bool:
    """Có công cụ đọc clipboard/selection nào không (dùng cho --doctor)."""
    return bool(shutil.which("wl-paste") or shutil.which("xclip"))
