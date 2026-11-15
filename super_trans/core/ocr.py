"""
Chụp ảnh màn hình vùng chọn và nhận diện ký tự OCR (Grim + Slurp + Tesseract)
Hỗ trợ đa ngôn ngữ đồng thời: Tiếng Anh (eng), Tiếng Pháp (fra), Tiếng Trung (chi_sim), Tiếng Việt (vie)
"""

import os
import shutil
import subprocess
import tempfile
from typing import List, Optional, Tuple

TARGET_LANGS = ("eng", "fra", "chi_sim", "vie")

USER_TESSDATA_DIR = os.path.expanduser("~/.local/share/tessdata")
SYSTEM_TESSDATA_DIRS = (
    "/usr/share/tesseract/tessdata",
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
    "/usr/local/share/tessdata",
)

OCR_TOOLS = ("slurp", "grim", "tesseract")


def _available_in(tessdata_dir: str) -> List[str]:
    """Các ngôn ngữ đích có sẵn trong một thư mục tessdata."""
    return [
        lang for lang in TARGET_LANGS
        if os.path.exists(os.path.join(tessdata_dir, f"{lang}.traineddata"))
    ]


def get_available_ocr_langs() -> Tuple[List[str], Optional[str]]:
    """
    Kiểm tra danh sách ngôn ngữ OCR và thư mục tessdata khả dụng.
    Ưu tiên thư mục người dùng, sau đó tới các vị trí cài đặt của hệ thống.
    """
    best_dir = None
    best_langs: List[str] = []

    for directory in (USER_TESSDATA_DIR, *SYSTEM_TESSDATA_DIRS):
        if not os.path.isdir(directory):
            continue
        langs = _available_in(directory)
        if len(langs) > len(best_langs):
            best_dir, best_langs = directory, langs
            if len(best_langs) == len(TARGET_LANGS):
                break

    if not best_langs:
        # Không tìm thấy tessdata riêng: để Tesseract dùng đường dẫn mặc định.
        return ["eng"], None

    return best_langs, best_dir


def select_ocr_languages(requested: Optional[str] = None,
                         available: Optional[List[str]] = None) -> str:
    """
    Lọc danh sách ngôn ngữ yêu cầu theo các gói thực sự đã cài.
    Ví dụ: "eng+fra+chi_sim+vie" -> "eng+fra" nếu chỉ có hai gói đầu.
    """
    if available is None:
        available, _ = get_available_ocr_langs()

    requested_langs = [part.strip() for part in (requested or "").split("+") if part.strip()]
    selected = [lang for lang in requested_langs if lang in available]
    if not selected:
        selected = available[:1] or ["eng"]

    # Loại bỏ trùng lặp nhưng giữ nguyên thứ tự
    return "+".join(dict.fromkeys(selected))


def missing_ocr_dependencies() -> List[str]:
    """Danh sách công cụ OCR còn thiếu trên hệ thống."""
    return [tool for tool in OCR_TOOLS if shutil.which(tool) is None]


def capture_and_ocr(lang: Optional[str] = None) -> str:
    """
    Kéo chuột chọn một vùng trên màn hình, chụp ảnh và OCR thành văn bản.
    Trả về chuỗi rỗng nếu người dùng hủy chọn hoặc không nhận diện được chữ.
    """
    missing = missing_ocr_dependencies()
    if missing:
        raise RuntimeError(
            "Thiếu công cụ OCR: " + ", ".join(missing)
            + ". Cài đặt bằng: sudo dnf install grim slurp tesseract"
        )

    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        raise RuntimeError("Không tìm thấy màn hình Wayland/X11 để chụp ảnh.")

    # 1. Chọn vùng màn hình qua slurp
    try:
        slurp_res = subprocess.run(["slurp"], capture_output=True, text=True, timeout=30)
        geometry = slurp_res.stdout.strip()
        if slurp_res.returncode != 0 or not geometry:
            return ""  # Người dùng nhấn Esc hoặc hủy
    except (OSError, subprocess.SubprocessError):
        return ""

    # 2. Chụp ảnh vùng chọn bằng grim
    fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="super-trans-ocr-")
    os.close(fd)

    try:
        grim_res = subprocess.run(
            ["grim", "-g", geometry, tmp_path],
            capture_output=True, text=True, timeout=8,
        )
        if grim_res.returncode != 0 or not os.path.exists(tmp_path):
            return ""

        # 3. Trích xuất text bằng tesseract
        available_langs, tess_dir = get_available_ocr_langs()
        lang_arg = select_ocr_languages(lang, available_langs)

        tess_cmd = ["tesseract"]
        if tess_dir:
            tess_cmd.extend(["--tessdata-dir", tess_dir])
        tess_cmd.extend([
            tmp_path,
            "stdout",
            "-l", lang_arg,
            "-c", "preserve_interword_spaces=1",
        ])

        tess_res = subprocess.run(
            tess_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if tess_res.returncode == 0:
            return tess_res.stdout.strip()
        return ""
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
