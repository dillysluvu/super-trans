"""
Tăng cường ảnh trước khi đưa vào Tesseract OCR.

Các bước xử lý (ưu tiên Pillow, fallback ImageMagick):
  - Chuyển sang ảnh xám.
  - Tự động đảo màu nếu nền tối (dark mode) để chữ thành tối trên nền sáng.
  - Cân bằng tương phản, làm nét nhẹ.
  - Phóng to ảnh nhỏ (ảnh chụp vùng UI thường chỉ vài trăm pixel).
  - Thêm viền trắng để Tesseract không cắt sát mép chữ.

Nếu không có Pillow lẫn ImageMagick, hàm trả về ảnh gốc và backend rỗng;
OCR vẫn hoạt động như trước.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

try:  # Pillow là phụ thuộc tùy chọn, không bắt buộc để chạy SuperTrans.
    from PIL import Image, ImageFilter, ImageOps
    PILLOW_AVAILABLE = True
except Exception:  # noqa: BLE001 - Pillow có thể lỗi import do thiếu thư viện hệ thống
    Image = None
    ImageFilter = None
    ImageOps = None
    PILLOW_AVAILABLE = False

MAX_TARGET_PIXELS = 24_000_000


def _temp_png() -> str:
    fd, path = tempfile.mkstemp(prefix="super-trans-ocr-prep-", suffix=".png")
    os.close(fd)
    return path


def _prepare_with_pillow(source: str, dest: str) -> bool:
    """Xử lý ảnh bằng Pillow. Trả về True nếu ghi được file đích."""
    if not PILLOW_AVAILABLE:
        return False

    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            gray = image.convert("L")

            # Ảnh nền tối (dark mode): đảo màu để chữ đen trên nền trắng.
            histogram = gray.histogram()
            total = max(1, sum(histogram))
            mean_luma = sum(i * count for i, count in enumerate(histogram)) / total
            if mean_luma < 110:
                gray = ImageOps.invert(gray)

            gray = ImageOps.autocontrast(gray, cutoff=1)

            # Phóng to ảnh nhỏ; ảnh lớn giữ nguyên để tránh tốn RAM.
            width, height = gray.size
            if width > 0 and width < 1600:
                scale = min(3.0, max(2.0, 1600.0 / width))
                new_w = max(1, int(width * scale))
                new_h = max(1, int(height * scale))
                if new_w * new_h <= MAX_TARGET_PIXELS:
                    gray = gray.resize((new_w, new_h), Image.LANCZOS)

            gray = gray.filter(
                ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=3)
            )

            border = max(8, int(gray.width * 0.01))
            gray = ImageOps.expand(gray, border=border, fill=255)

            gray.save(dest, format="PNG", optimize=True)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:  # noqa: BLE001 - lỗi ảnh không được làm hỏng OCR
        return False


def _imagemagick_binary() -> Optional[str]:
    for name in ("magick", "convert"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _prepare_with_imagemagick(source: str, dest: str) -> bool:
    """Fallback khi thiếu Pillow."""
    binary = _imagemagick_binary()
    if not binary:
        return False

    try:
        res = subprocess.run(
            [
                binary, source,
                "-colorspace", "Gray",
                "-auto-level",
                "-resize", "200%",
                "-sharpen", "0x1",
                "-bordercolor", "white",
                "-border", "12",
                dest,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return res.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 0
    except (OSError, subprocess.SubprocessError):
        return False


def backend() -> str:
    """Backend tiền xử lý đang dùng: 'pillow', 'imagemagick' hoặc ''."""
    if PILLOW_AVAILABLE:
        return "pillow"
    if _imagemagick_binary():
        return "imagemagick"
    return ""


def preprocess_image(source: str,
                     dest: Optional[str] = None) -> Tuple[str, str]:
    """
    Tạo ảnh đã tăng cường cho OCR.

    Trả về ``(đường_dẫn_ảnh, backend)``. Nếu không xử lý được, trả về
    ``(source, "")``. Người gọi chịu trách nhiệm xóa file nếu đường dẫn khác
    ảnh gốc.
    """
    if not source or not os.path.isfile(source):
        return source, ""

    target = dest or _temp_png()
    try:
        if _prepare_with_pillow(source, target):
            return target, "pillow"
        if _prepare_with_imagemagick(source, target):
            return target, "imagemagick"
    except Exception:  # noqa: BLE001
        pass

    if target != source and os.path.exists(target):
        try:
            os.remove(target)
        except OSError:
            pass
    return source, ""


def status() -> dict:
    """Thông tin cho lệnh --doctor."""
    name = backend()
    return {
        "available": bool(name),
        "backend": name,
        "pillow": PILLOW_AVAILABLE,
        "imagemagick": _imagemagick_binary() is not None,
    }
