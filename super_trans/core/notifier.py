"""
Quản lý hiển thị kết quả dịch thuật tích hợp các công cụ sẵn có
"""

import subprocess
import shutil
from super_trans.core.launcher import show_in_launcher, replace_selection_in_place
from super_trans.core.osd import show_osd

def send_dms_toast(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast") -> bool:
    """Hiển thị toast trực tiếp trên thanh DMS bar / Dynamic Island."""
    if not shutil.which("dms"):
        return False

    src_display = src_lang.upper() if src_lang else "AUTO"
    tgt_display = tgt_lang.upper() if tgt_lang else "VI"
    title = f"🌐 [{src_display} ➔ {tgt_display}] ({engine_name})"

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
                   mode: str = "launcher", timeout_ms: int = 6000) -> bool:
    """
    Điểm tập trung hiển thị output:
    - 'launcher': Mở trực tiếp trong DMS Launcher / Spotlight có sẵn (Đồng nhất 100%)
    - 'replace': Thay thế trực tiếp tại chỗ bằng wtype (0 cửa sổ, 0 thông báo)
    - 'osd': Thẻ OSD nổi Wayland
    - 'dms_toast': Toast trực tiếp trên Dynamic Island của DMS
    - 'notification': Thông báo notify-send
    """
    if mode == "launcher":
        action = show_in_launcher(original, translated, src_lang, tgt_lang, engine_name)
        return bool(action)

    if mode == "replace":
        return replace_selection_in_place(translated)

    if mode == "osd":
        timeout_sec = max(4.0, timeout_ms / 1000.0)
        if len(translated) > 200:
            timeout_sec = 12.0
        return show_osd(original, translated, src_lang, tgt_lang, engine_name, timeout_sec)

    if mode == "dms_toast":
        if send_dms_toast(original, translated, src_lang, tgt_lang, engine_name):
            return True
        mode = "notification"

    return send_notification(original, translated, src_lang, tgt_lang, engine_name, timeout_ms)
