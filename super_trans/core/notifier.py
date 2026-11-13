"""
Quản lý hiển thị kết quả dịch thuật (Wayland OSD Floating Card, DMS Toast, Notification)
"""

import subprocess
import shutil
from super_trans.core.osd import show_osd

def send_dms_toast(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast") -> bool:
    """Hiển thị toast trực tiếp trên thanh DMS bar / Dynamic Island."""
    if not shutil.which("dms"):
        return False

    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 [{src_display} ➔ {tgt_display}] ({engine_name})"

    # Cắt ngắn bản dịch nếu cần cho thanh bar
    summary = translated.replace("\n", " ").strip()
    if len(summary) > 90:
        summary = summary[:87] + "..."

    try:
        subprocess.run(
            ["dms", "ipc", "call", "toast", "infoWith", title, summary, "", "trans"],
            capture_output=True,
            timeout=2
        )
        return True
    except Exception:
        return False

def send_notification(original: str, translated: str, src_lang: str = "auto",
                      tgt_lang: str = "vi", engine_name: str = "Fast",
                      timeout_ms: int = 6000) -> bool:
    """Hiển thị notification desktop thông thường qua notify-send."""
    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 SuperTrans [{src_display} ➔ {tgt_display}] ({engine_name})"

    orig_preview = original.strip()
    if len(orig_preview) > 120:
        orig_preview = orig_preview[:117] + "..."

    trans_preview = translated.strip()
    if len(trans_preview) > 300:
        trans_preview = trans_preview[:297] + "..."

    body = f"<b>{orig_preview}</b>\n───────────────────\n{trans_preview}"

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
    return False

def display_result(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast",
                   mode: str = "osd", timeout_ms: int = 6000) -> bool:
    """
    Điểm tập trung hiển thị output theo mode:
    - 'osd': Wayland Layer-Shell Floating Card (Tối giản, đẹp mắt, đồng nhất Niri & DMS)
    - 'dms_toast': Toast trực tiếp trên Dynamic Island của DMS
    - 'notification': Thông báo notify-send
    """
    if mode == "osd":
        # Thử khởi chạy OSD Card nổi cực đẹp
        timeout_sec = max(4.0, timeout_ms / 1000.0)
        # Nếu là bài dịch dài hoặc AI, tăng thời gian đọc lên 12s
        if len(translated) > 200:
            timeout_sec = 12.0

        success = show_osd(
            original=original,
            translated=translated,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            engine=engine_name,
            timeout_sec=timeout_sec
        )
        if success:
            return True
        # Fallback sang dms_toast nếu OSD không chạy được
        mode = "dms_toast"

    if mode == "dms_toast":
        if send_dms_toast(original, translated, src_lang, tgt_lang, engine_name):
            return True
        mode = "notification"

    return send_notification(original, translated, src_lang, tgt_lang, engine_name, timeout_ms)
