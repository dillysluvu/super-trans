"""
Quản lý cấu hình SuperTrans
"""

import json
import os
from typing import Dict, Any

CONFIG_DIR = os.path.expanduser("~/.config/super-trans")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_engine": "fast",                 # "fast" (Google GTX) hoặc "ai" (OpenCode)
    "ai_model": "opencode/deepseek-v4.1-flash-free",
    "primary_target_lang": "vi",              # Dịch sang Tiếng Việt nếu nguồn là ngoại ngữ
    "secondary_target_lang": "en",            # Dịch sang Tiếng Anh nếu nguồn là Tiếng Việt
    "auto_copy_to_clipboard": True,          # Tự động copy bản dịch vào Clipboard
    "notification_timeout_ms": 6000,          # Thời gian hiện notification (ms)
    "show_popup_on_ai": True,                # Mở popup chi tiết khi dùng AI mode
    "ocr_lang": "eng",                        # Ngôn ngữ mặc định cho Tesseract OCR
}

def load_config() -> Dict[str, Any]:
    """Tải cấu hình người dùng hoặc tạo mặc định nếu chưa có."""
    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError:
            pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(user_conf)
                return merged
        except Exception:
            return DEFAULT_CONFIG.copy()

    # Lưu file mẫu lần đầu
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

    return DEFAULT_CONFIG.copy()
