"""
Chụp ảnh màn hình vùng chọn và nhận diện ký tự OCR (Grim + Slurp + Tesseract)
Hỗ trợ đa ngôn ngữ đồng thời: Tiếng Anh (eng), Tiếng Pháp (fra), Tiếng Trung (chi_sim), Tiếng Việt (vie)
"""

import subprocess
import shutil
import tempfile
import os

USER_TESSDATA_DIR = os.path.expanduser("~/.local/share/tessdata")

def get_available_ocr_langs() -> tuple[list[str], str]:
    """Kiểm tra danh sách ngôn ngữ OCR và thư mục tessdata khả dụng."""
    tessdata_dir = None
    langs = ["eng"]

    if os.path.exists(USER_TESSDATA_DIR):
        tessdata_dir = USER_TESSDATA_DIR
        avail = []
        for l in ["eng", "fra", "chi_sim", "vie"]:
            if os.path.exists(os.path.join(USER_TESSDATA_DIR, f"{l}.traineddata")):
                avail.append(l)
        if avail:
            langs = avail

    return langs, tessdata_dir

def capture_and_ocr(lang: str = None) -> str:
    """
    Kéo chuột chọn một vùng trên màn hình, chụp ảnh và OCR thành văn bản.
    Tự động hỗ trợ đồng thời cả tiếng Anh, Pháp, Trung và Việt.
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
        avail_langs, tess_dir = get_available_ocr_langs()
        lang_arg = lang if lang else "+".join(avail_langs)

        tess_cmd = ["tesseract"]
        if tess_dir:
            tess_cmd.extend(["--tessdata-dir", tess_dir])
        tess_cmd.extend([tmp_path, "stdout", "-l", lang_arg])

        tess_res = subprocess.run(
            tess_cmd,
            capture_output=True,
            text=True,
            timeout=15
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
