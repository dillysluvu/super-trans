"""
Tiến trình nền xử lý nút bấm trên Dynamic Island.

Được ``island.show_in_island`` khởi chạy sau khi publish. Payload nhận qua
stdin để văn bản không xuất hiện trong danh sách tiến trình.
"""

import json
import sys
import time
from typing import Any, Dict

from super_trans.core import dms, presentation
from super_trans.core.clipboard import set_clipboard_text
from super_trans.core.launcher import open_in_dms_notepad
from super_trans.engines.opencode_engine import OpenCodeEngine

MAX_LIFETIME_SEC = 600.0
POLL_INTERVAL_SEC = 0.35
LIST_CHECK_INTERVAL_SEC = 1.5


def handle_action(action: str, payload: Dict[str, Any]) -> str:
    """
    Xử lý một action từ island.

    Trả ``"close"`` nếu nên đóng island, ``"keep"`` nếu giữ tiếp.
    """
    translated = str(payload.get("translated") or "")
    original = str(payload.get("original") or "")
    src_lang = str(payload.get("src_lang") or "auto")
    tgt_lang = str(payload.get("tgt_lang") or "vi")

    if action == "copy":
        if set_clipboard_text(translated):
            dms.toast(
                "📋 Đã sao chép",
                presentation.ellipsis(translated, 80),
                "",
                "trans",
            )
        else:
            dms.toast("⚠ SuperTrans", "Không sao chép được bản dịch.", "", "trans")
        return "keep"

    if action == "analyze":
        analysis = str(payload.get("analysis") or "").strip()
        detected_src = src_lang

        if not analysis:
            dms.toast(
                "🧠 SuperTrans",
                "Đang phân tích bằng OpenCode AI…",
                "",
                "trans",
            )
            try:
                engine = OpenCodeEngine(
                    model=str(payload.get("ai_model") or "") or None,
                    timeout=float(payload.get("ai_timeout") or 120.0),
                )
                _, analysis, detected_src = engine.analyze(
                    original, src_lang=src_lang, tgt_lang=tgt_lang,
                )
            except Exception as exc:  # noqa: BLE001 - báo lỗi cho mọi trường hợp
                dms.toast("⚠ SuperTrans", str(exc)[:140], "", "trans")
                return "keep"

        opened = open_in_dms_notepad(
            original, analysis, detected_src, tgt_lang,
        )
        if not opened:
            dms.notify(
                "🌐 SuperTrans - Phân tích AI",
                analysis[:1000],
                timeout_ms=12000,
            )
        return "close"

    return "keep"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (TypeError, ValueError):
        return 1
    if not isinstance(payload, dict):
        return 1

    source = str(payload.get("source") or "")
    activity_id = str(payload.get("id") or "")
    if not source or not activity_id:
        return 1

    try:
        duration = max(
            1.0, float(payload.get("duration_ms") or 10000) / 1000.0,
        )
    except (TypeError, ValueError):
        duration = 10.0

    started = time.monotonic()
    hard_deadline = started + MAX_LIFETIME_SEC
    soft_deadline = started + max(30.0, duration + 10.0)
    next_list_check = started + LIST_CHECK_INTERVAL_SEC
    list_readable = True

    while time.monotonic() < hard_deadline:
        for event in dms.island_poll_actions(source):
            if not isinstance(event, dict):
                continue
            action = str(event.get("action") or "")
            if not action:
                continue
            if handle_action(action, payload) == "close":
                dms.island_remove(source, activity_id)
                return 0

        now = time.monotonic()
        if now >= next_list_check:
            entries = dms.island_list()
            if entries is None:
                list_readable = False
            else:
                list_readable = True
                present = any(
                    isinstance(entry, dict)
                    and entry.get("source") == source
                    and entry.get("id") == activity_id
                    for entry in entries
                )
                if not present:
                    return 0
            next_list_check = now + LIST_CHECK_INTERVAL_SEC

        if not list_readable and now >= soft_deadline:
            return 0

        time.sleep(POLL_INTERVAL_SEC)

    dms.island_remove(source, activity_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
