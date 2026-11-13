"""
Chụp ảnh màn hình vùng chọn và nhận diện ký tự OCR (Grim + Slurp + Tesseract)
"""

import subprocess
import shutil
import tempfile
import os

def capture_and_ocr(lang: str = "eng") -> str:
    """
    Kéo chuột chọn một vùng trên màn hình, chụp ảnh và OCR thành văn bản.
    Trả về chuỗi rỗng nếu người dùng hủy chọn hoặc OCR thất bại.
    """
    if not (shutil.which("slurp") and shutil.which("grim") and shutil.which("tesseract")):
        raise RuntimeError("Cần cài đặt slurp, grim và tesseract để dùng tính năng OCR.")

    # 1. Chọn vùng màn hình qua slurp
    try:
        slurp_res = subprocess.run(["slurp"], capture_output=True, text=True, timeout=30)
        geometry = slurp_res.stdout.strip()
        if slurp_res.returncode != 0 or not geometry:
            return "" # Người dùng nhấn Esc hoặc hủy
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""

    # 2. Chụp ảnh vùng chọn bằng grim
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        grim_res = subprocess.run(["grim", "-g", geometry, tmp_path], capture_output=True, timeout=5)
        if grim_res.returncode != 0 or not os.path.exists(tmp_path):
            return ""

        # 3. Trích xuất text bằng tesseract
        tess_res = subprocess.run(
            ["tesseract", tmp_path, "stdout", "-l", lang],
            capture_output=True,
            text=True,
            timeout=10
        )
        if tess_res.returncode == 0:
            extracted = tess_res.stdout.strip()
            return extracted
        return ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
