"""
Quản lý hiển thị kết quả dịch thuật tích hợp các công cụ sẵn có.
"""

import html
import shutil
import subprocess

from super_trans.core import dms, presentation
from super_trans.core.island import show_in_island
from super_trans.core.launcher import show_in_launcher, replace_selection_in_place
from super_trans.core.osd import show_osd, osd_available


def send_dms_toast(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast",
                   context: str = "") -> bool:
    """Toast tối giản: dòng đầu ``gốc : nghĩa``, dòng sau engine · ngữ cảnh."""
    if not dms.available():
        return False

    title = presentation.compact_pair(original, translated, 160)
    details = presentation.context_line(
        engine_name, context, src_lang, tgt_lang, 180,
    )
    return dms.toast(title, details, "", "trans")


def send_notification(original: str, translated: str, src_lang: str = "auto",
                      tgt_lang: str = "vi", engine_name: str = "Fast",
                      timeout_ms: int = 6000, context: str = "") -> bool:
    """Notification desktop tối giản, fallback notify-send."""
    title = presentation.compact_pair(original, translated, 180)
    details = presentation.context_line(
        engine_name, context, src_lang, tgt_lang, 200,
    )

    trans_preview = translated.strip()
    if len(trans_preview) > 300:
        trans_preview = trans_preview[:297] + "..."
    trans_preview = html.escape(trans_preview)

    body = trans_preview
    if details:
        body += f"\n\n{html.escape(details)}"

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
                   mode: str = "island", timeout_ms: int = 6000,
                   ai_model: str = None, ai_timeout: float = 120.0,
                   analysis: str = "", context: str = "",
                   island_timeout_ms: int = 10000,
                   pending=None) -> bool:
    """
    Điểm tập trung hiển thị output:
    - 'island': Dynamic Island của DMS, tối giản ``gốc : nghĩa``
    - 'launcher': DMS Launcher / Spotlight (fallback fuzzel)
    - 'replace': thay thế tại chỗ bằng DMS/wtype (0 cửa sổ)
    - 'osd': thẻ OSD nổi Wayland (fallback notification)
    - 'dms_toast': toast trên Dynamic Island của DMS
    - 'notification': notification desktop
    - 'none': không hiển thị
    """
    if mode == "none":
        return True

    if not context and analysis:
        context = presentation.short_context(analysis)
    if context and translated and context.strip() == translated.strip():
        # LLM không tách được phân tích: đừng lặp lại y nguyên bản dịch ở phụ đề.
        context = ""

    if mode == "island":
        if show_in_island(
            original, translated, src_lang, tgt_lang, engine_name,
            context=context, analysis=analysis,
            ai_model=ai_model, ai_timeout=ai_timeout,
            timeout_ms=island_timeout_ms, pending=pending,
        ):
            return True
        # Island không khả dụng: quay lại launcher để vẫn thao tác được.
        mode = "launcher"

    if mode == "launcher":
        action = show_in_launcher(
            original, translated, src_lang, tgt_lang, engine_name,
            ai_model=ai_model, ai_timeout=ai_timeout, analysis=analysis,
        )
        return bool(action)

    if mode == "replace":
        return replace_selection_in_place(
            translated,
            original=original,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            engine=engine_name,
        )

    if mode == "osd":
        timeout_sec = max(4.0, timeout_ms / 1000.0)
        if len(translated) > 200:
            timeout_sec = 12.0
        if osd_available() and show_osd(original, translated, src_lang, tgt_lang, engine_name, timeout_sec):
            return True
        mode = "notification"

    if mode == "dms_toast":
        if send_dms_toast(
            original, translated, src_lang, tgt_lang, engine_name,
            context=context,
        ):
            return True
        mode = "notification"

    return send_notification(
        original, translated, src_lang, tgt_lang, engine_name,
        timeout_ms, context=context,
    )
