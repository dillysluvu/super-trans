"""
Giao diện nhập liệu nhanh và hiển thị chi tiết (Fuzzel / Zenity)
"""

import subprocess
import shutil
import tempfile
import os

def prompt_input() -> str:
    """Mở hộp thoại nhập văn bản nhanh từ bàn phím."""
    # 1. Thử fuzzel (native Wayland, cực nhanh và đẹp)
    if shutil.which("fuzzel"):
        try:
            res = subprocess.run(
                ["fuzzel", "--dmenu", "--prompt-only=🌐 Dịch > ", "--width=45", "--lines=0"],
                capture_output=True,
                text=True,
                timeout=60
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

    # 2. Thử zenity
    if shutil.which("zenity"):
        try:
            res = subprocess.run(
                [
                    "zenity", "--entry",
                    "--title=SuperTrans - Nhập văn bản cần dịch",
                    "--text=Nhập hoặc dán văn bản cần dịch:",
                    "--width=450"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            text = res.stdout.strip()
            if text:
                return text
        except Exception:
            pass

    return ""

def show_detail_dialog(title: str, text: str):
    """Mở cửa sổ xem chi tiết bản dịch (thích hợp cho bài dài hoặc phân tích AI)."""
    if shutil.which("zenity"):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        try:
            subprocess.Popen([
                "zenity", "--text-info",
                f"--title={title}",
                f"--filename={tmp_path}",
                "--width=650",
                "--height=450",
                "--font=Sans 11"
            ])
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
