"""
Quản lý gửi thông báo màn hình (notify-send / dms notify)
"""

import subprocess
import shutil

def send_notification(original: str, translated: str, src_lang: str = "auto", tgt_lang: str = "vi",
                      engine_name: str = "Fast", timeout_ms: int = 6000) -> bool:
    """Hiển thị thông báo kết quả dịch trên màn hình."""
    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 SuperTrans [{src_display} ➔ {tgt_display}] ({engine_name})"

    # Cắt ngắn nếu quá dài cho notification, tránh tràn màn hình
    orig_preview = original.strip()
    if len(orig_preview) > 120:
        orig_preview = orig_preview[:117] + "..."

    trans_preview = translated.strip()
    if len(trans_preview) > 300:
        trans_preview = trans_preview[:297] + "..."

    body = f"<b>{orig_preview}</b>\n───────────────────\n{trans_preview}"

    # 1. Thử notify-send
    if shutil.which("notify-send"):
        try:
            cmd = [
                "notify-send",
                "-a", "SuperTrans",
                "-i", "accessories-dictionary",
                "-t", str(timeout_ms),
                title,
                body
            ]
            subprocess.run(cmd, capture_output=True, timeout=3)
            return True
        except Exception:
            pass

    # 2. Thử dms notify
    if shutil.which("dms"):
        try:
            cmd = [
                "dms", "notify",
                "-a", "SuperTrans",
                "-t", str(timeout_ms),
                title,
                f"{orig_preview}\n---\n{trans_preview}"
            ]
            subprocess.run(cmd, capture_output=True, timeout=3)
            return True
        except Exception:
            pass

    return False
