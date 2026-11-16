"""
Quản lý cấu hình SuperTrans
"""

import json
import os
from typing import Any, Dict

CONFIG_DIR = os.path.expanduser("~/.config/super-trans")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

VALID_OUTPUT_MODES = {"launcher", "replace", "osd", "dms_toast", "notification", "none"}
VALID_ENGINES = {"fast", "ai"}

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_engine": "fast",                 # "fast" (Google GTX) hoặc "ai" (OpenCode)
    "output_mode": "launcher",                # launcher | replace | osd | dms_toast | notification | none
    "ai_model": "opencode/deepseek-v4.1-flash-free",
    "ai_timeout_sec": 120,                    # Thời gian chờ tối đa cho OpenCode AI
    "primary_target_lang": "vi",              # Dịch sang Tiếng Việt nếu nguồn là ngoại ngữ
    "secondary_target_lang": "en",            # Dịch sang Tiếng Anh nếu nguồn là Tiếng Việt
    "auto_copy_to_clipboard": True,           # Tự động copy bản dịch vào Clipboard DMS
    "notification_timeout_ms": 6000,          # Thời gian timeout (ms)
    "show_popup_on_ai": True,                 # Mở bài phân tích AI trong DMS Notepad
    "ocr_lang": "eng+fra+chi_sim+vie",        # Ngôn ngữ mặc định cho Tesseract OCR
    "ocr_preprocess": True,                   # Tăng cường ảnh trước khi OCR (Pillow/ImageMagick)
    "ocr_psm": 3,                             # Page Segmentation Mode của Tesseract (0-13)
    "cache_enabled": True,                    # Cache bản dịch + lưu lịch sử SQLite
    "history_limit": 500,                     # Số mục lịch sử tối đa giữ lại
}

_INT_RANGES = {
    "notification_timeout_ms": (1000, 60000),
    "ai_timeout_sec": (10, 600),
    "ocr_psm": (0, 13),
    "history_limit": (10, 10000),
}


def _sanitize(user_conf: Dict[str, Any]) -> Dict[str, Any]:
    """Hợp nhất cấu hình người dùng với mặc định và loại bỏ giá trị không hợp lệ."""
    merged = DEFAULT_CONFIG.copy()
    if isinstance(user_conf, dict):
        merged.update({key: value for key, value in user_conf.items() if key in DEFAULT_CONFIG})

    if merged.get("default_engine") not in VALID_ENGINES:
        merged["default_engine"] = DEFAULT_CONFIG["default_engine"]

    if merged.get("output_mode") not in VALID_OUTPUT_MODES:
        merged["output_mode"] = DEFAULT_CONFIG["output_mode"]

    for key, (low, high) in _INT_RANGES.items():
        try:
            value = int(merged.get(key))
        except (TypeError, ValueError):
            value = DEFAULT_CONFIG[key]
        merged[key] = max(low, min(high, value))

    for key in ("auto_copy_to_clipboard", "show_popup_on_ai",
                "ocr_preprocess", "cache_enabled"):
        if not isinstance(merged.get(key), bool):
            merged[key] = DEFAULT_CONFIG[key]

    for key in ("ai_model", "primary_target_lang", "secondary_target_lang", "ocr_lang"):
        if not isinstance(merged.get(key), str) or not merged[key].strip():
            merged[key] = DEFAULT_CONFIG[key]

    return merged


def load_config() -> Dict[str, Any]:
    """Tải cấu hình người dùng hoặc tạo mặc định nếu chưa có."""
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError:
            pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                return _sanitize(json.load(handle))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_CONFIG.copy()

    # Lưu file mẫu lần đầu
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass

    return DEFAULT_CONFIG.copy()
