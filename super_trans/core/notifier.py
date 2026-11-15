"""
Quản lý hiển thị kết quả dịch thuật tích hợp các công cụ sẵn có.
"""

import html
import shutil
import subprocess

from super_trans.core import dms
from super_trans.core.launcher import show_in_launcher, replace_selection_in_place
from super_trans.core.osd import show_osd, osd_available


def send_dms_toast(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast") -> bool:
    """Hiển thị toast trực tiếp trên thanh DMS bar / Dynamic Island."""
    if not dms.available():
        return False

    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 [{src_display} ➔ {tgt_display}] ({engine_name})"

    summary = translated.replace("\n", " ").strip()
    if len(summary) > 90:
        summary = summary[:87] + "..."

    return dms.toast(title, summary, "", "trans")


def send_notification(original: str, translated: str, src_lang: str = "auto",
                      tgt_lang: str = "vi", engine_name: str = "Fast",
                      timeout_ms: int = 6000) -> bool:
    """Hiển thị notification desktop qua DMS, fallback notify-send."""
    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 SuperTrans [{src_display} ➔ {tgt_display}] ({engine_name})"

    orig_preview = original.strip()
    if len(orig_preview) > 120:
        orig_preview = orig_preview[:117] + "..."
    orig_preview = html.escape(orig_preview)

    trans_preview = translated.strip()
    if len(trans_preview) > 300:
        trans_preview = trans_preview[:297] + "..."
    trans_preview = html.escape(trans_preview)

    body = f"<b>{orig_preview}</b>\n───────────────────\n{trans_preview}"

    # 1. DMS Notification: đồng nhất với Dynamic Island / notification center
    if dms.notify(title, body, timeout_ms=timeout_ms):
        return True

    # 2. Fallback notify-send trên các desktop khác
    if shutil.which("notify-send"):
        try:
            cmd = [
                "notify-send",
                "-a", "SuperTrans",
                "-i", "accessories-dictionary",
                "-t", str(timeout_ms),
                title,
                body,
            ]
            subprocess.run(cmd, capture_output=True, timeout=3)
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def display_result(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast",
                   mode: str = "launcher", timeout_ms: int = 6000,
                   ai_model: str = None, ai_timeout: float = 120.0) -> bool:
    """
    Điểm tập trung hiển thị output:
    - 'launcher': DMS Launcher / Spotlight (fallback fuzzel)
    - 'replace': thay thế tại chỗ bằng DMS/wtype (0 cửa sổ)
    - 'osd': thẻ OSD nổi Wayland (fallback notification)
    - 'dms_toast': toast trên Dynamic Island của DMS
    - 'notification': notification desktop
    - 'none': không hiển thị
    """
    if mode == "none":
        return True

    if mode == "launcher":
        action = show_in_launcher(
            original, translated, src_lang, tgt_lang, engine_name,
            ai_model=ai_model, ai_timeout=ai_timeout,
        )
        return bool(action)

    if mode == "replace":
        return replace_selection_in_place(translated)

    if mode == "osd":
        timeout_sec = max(4.0, timeout_ms / 1000.0)
        if len(translated) > 200:
            timeout_sec = 12.0
        if osd_available() and show_osd(original, translated, src_lang, tgt_lang, engine_name, timeout_sec):
            return True
        mode = "notification"

    if mode == "dms_toast":
        if send_dms_toast(original, translated, src_lang, tgt_lang, engine_name):
            return True
        mode = "notification"

    return send_notification(original, translated, src_lang, tgt_lang, engine_name, timeout_ms)
