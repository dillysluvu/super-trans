"""
Chụp ảnh màn hình vùng chọn và nhận diện ký tự OCR (Grim + Slurp + Tesseract)
Hỗ trợ đa ngôn ngữ đồng thời: Tiếng Anh (eng), Tiếng Pháp (fra), Tiếng Trung (chi_sim), Tiếng Việt (vie)

Ngoài chụp vùng màn hình, module còn hỗ trợ:
  - OCR một file ảnh có sẵn (``image_path``).
  - OCR ảnh đang có trong clipboard (``from_clipboard``).
  - Tăng cường ảnh trước khi nhận diện (``preprocess``).
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
CLIPBOARD_IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp", "image/bmp")


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


def missing_ocr_dependencies(need_capture: bool = True,
                             need_clipboard: bool = False) -> List[str]:
    """Danh sách công cụ OCR còn thiếu trên hệ thống."""
    tools = list(OCR_TOOLS) if need_capture else ["tesseract"]
    if need_clipboard:
        tools.append("wl-paste")
    return [tool for tool in tools if shutil.which(tool) is None]


def _temp_file(suffix: str, prefix: str = "super-trans-ocr-") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def _grab_clipboard_image() -> str:
    """Lưu ảnh trong clipboard ra file tạm. Trả về đường dẫn hoặc chuỗi rỗng."""
    if not shutil.which("wl-paste"):
        raise RuntimeError(
            "Cần wl-paste (wl-clipboard) để đọc ảnh từ clipboard."
        )

    for mime in CLIPBOARD_IMAGE_TYPES:
        path = _temp_file(".png")
        try:
            with open(path, "wb") as handle:
                res = subprocess.run(
                    ["wl-paste", "--type", mime],
                    stdout=handle,
                    stderr=subprocess.PIPE,
                    timeout=8,
                )
            if res.returncode == 0 and os.path.getsize(path) > 0:
                return path
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            os.remove(path)
        except OSError:
            pass

    raise RuntimeError("Clipboard hiện không chứa ảnh (PNG/JPEG/WebP/BMP).")


def _capture_region() -> str:
    """Chọn vùng bằng slurp rồi chụp bằng grim. Trả về file tạm hoặc rỗng."""
    try:
        slurp_res = subprocess.run(["slurp"], capture_output=True, text=True, timeout=30)
        geometry = slurp_res.stdout.strip()
        if slurp_res.returncode != 0 or not geometry:
            return ""  # Người dùng nhấn Esc hoặc hủy
    except (OSError, subprocess.SubprocessError):
        return ""

    path = _temp_file(".png")
    try:
        grim_res = subprocess.run(
            ["grim", "-g", geometry, path],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if grim_res.returncode != 0 or not os.path.exists(path) or os.path.getsize(path) == 0:
            try:
                os.remove(path)
            except OSError:
                pass
            return ""
        return path
    except (OSError, subprocess.SubprocessError):
        try:
            os.remove(path)
        except OSError:
            pass
        return ""


def capture_and_ocr(lang: Optional[str] = None, preprocess: bool = True,
                    image_path: Optional[str] = None,
                    from_clipboard: bool = False,
                    psm: int = 3) -> str:
    """
    Nhận diện chữ từ vùng màn hình, file ảnh hoặc clipboard.

    - Không truyền ``image_path``/``from_clipboard``: kéo chuột chọn vùng.
    - Trả về chuỗi rỗng nếu người dùng hủy chọn hoặc không nhận diện được chữ.
    - Ném RuntimeError khi thiếu công cụ hoặc ảnh đầu vào không hợp lệ.
    """
    need_capture = not image_path and not from_clipboard
    missing = missing_ocr_dependencies(
        need_capture=need_capture,
        need_clipboard=from_clipboard,
    )
    if missing:
        raise RuntimeError(
            "Thiếu công cụ OCR: " + ", ".join(missing)
            + ". Cài đặt bằng: sudo dnf install grim slurp tesseract "
              "wl-clipboard"
        )

    if need_capture and not (
        os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    ):
        raise RuntimeError("Không tìm thấy màn hình Wayland/X11 để chụp ảnh.")

    if from_clipboard and not os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError(
            "Đọc ảnh từ clipboard cần phiên Wayland (WAYLAND_DISPLAY)."
        )

    if image_path and not os.path.isfile(image_path):
        raise RuntimeError(f"Không tìm thấy file ảnh: {image_path}")

    temp_paths = []

    try:
        # 1. Lấy ảnh đầu vào
        if image_path:
            source_path = image_path
        elif from_clipboard:
            source_path = _grab_clipboard_image()
            temp_paths.append(source_path)
        else:
            source_path = _capture_region()
            if not source_path:
                return ""
            temp_paths.append(source_path)

        # 2. Tăng cường ảnh (nếu bật và có backend). Import muộn để không
        #    kéo Pillow vào mọi lần dịch thông thường.
        ocr_path = source_path
        if preprocess:
            from super_trans.core.image_prep import preprocess_image
            processed_path, _backend = preprocess_image(source_path)
            if processed_path != source_path:
                temp_paths.append(processed_path)
                ocr_path = processed_path

        # 3. Trích xuất text bằng tesseract
        available_langs, tess_dir = get_available_ocr_langs()
        lang_arg = select_ocr_languages(lang, available_langs)

        tess_cmd = ["tesseract"]
        if tess_dir:
            tess_cmd.extend(["--tessdata-dir", tess_dir])
        tess_cmd.extend([
            ocr_path,
            "stdout",
            "-l", lang_arg,
        ])
        if 0 <= int(psm) <= 13:
            tess_cmd.extend(["--psm", str(int(psm))])
        tess_cmd.extend([
            "-c", "preserve_interword_spaces=1",
            "-c", "user_defined_dpi=300",
        ])

        tess_res = subprocess.run(
            tess_cmd,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if tess_res.returncode == 0:
            return tess_res.stdout.strip()
        return ""
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        for path in temp_paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
