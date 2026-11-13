"""
Tương tác Clipboard & Selection trên Wayland / X11
"""

import subprocess
import shutil

def get_selection_text() -> str:
    """
    Lấy văn bản đang được bôi đen (PRIMARY selection).
    Nếu không có, fallback lấy văn bản trong CLIPBOARD thông thường.
    """
    # 1. Thử wl-paste --primary (Wayland chuột bôi đen)
    if shutil.which("wl-paste"):
        try:
            res = subprocess.run(
                ["wl-paste", "--primary", "--no-newline"],
                capture_output=True,
                text=True,
                timeout=1
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

        # Fallback sang wl-paste thông thường
        try:
            res = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                timeout=1
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

    # 2. Fallback xclip nếu cần
    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-o", "-selection", "primary"],
                capture_output=True,
                text=True,
                timeout=1
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["xclip", "-o", "-selection", "clipboard"],
                capture_output=True,
                text=True,
                timeout=1
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

    return ""

def set_clipboard_text(text: str) -> bool:
    """Sao chép văn bản vào clipboard hệ thống."""
    if not text:
        return False

    if shutil.which("wl-copy"):
        try:
            proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=2)
            return proc.returncode == 0
        except Exception:
            pass

    if shutil.which("xclip"):
        try:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=2)
            return proc.returncode == 0
        except Exception:
            pass

    return False
