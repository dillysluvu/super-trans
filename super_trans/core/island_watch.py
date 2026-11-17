"""
Tiến trình nền xử lý nút bấm trên Dynamic Island.

Được ``island.show_in_island`` khởi chạy sau khi publish. Payload nhận qua
stdin để văn bản không xuất hiện trong danh sách tiến trình.
"""

import json
import select
import sys
import time
from typing import Any, Dict, Optional

from super_trans.core import dms, native, presentation
from super_trans.core.clipboard import set_clipboard_text
from super_trans.core.launcher import open_in_dms_notepad
from super_trans.engines.opencode_engine import OpenCodeEngine

MAX_LIFETIME_SEC = 600.0
POLL_INTERVAL_SEC = 0.35
LIST_CHECK_INTERVAL_SEC = 1.5
NATIVE_READY_TIMEOUT_SEC = 2.0


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


def _remove_activity(source: str, activity_id: str) -> None:
    if not native.island_remove(source, activity_id):
        dms.island_remove(source, activity_id)


def _parse_event(line: str) -> Optional[Dict[str, Any]]:
    """Đọc một dòng JSON từ watcher Rust."""
    try:
        event = json.loads(line or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(event, dict):
        return None
    if event.get("type") == "action" or event.get("action"):
        return event
    return None


def _handle_event(event: Dict[str, Any], payload: Dict[str, Any]) -> str:
    action = str(event.get("action") or "")
    if not action:
        return "keep"
    return handle_action(action, payload)


def _terminate(proc) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except Exception:  # noqa: BLE001 - tiến trình con có thể đã thoát
            proc.kill()


def _run_native_watcher(source: str, activity_id: str, duration: float,
                        payload: Dict[str, Any]) -> Optional[int]:
    """
    Chạy watcher Rust. Trả None nếu helper không sẵn sàng để fallback Python.

    Watcher Rust poll IPC trực tiếp mỗi ~80ms nên nút bấm phản hồi nhanh hơn
    hẳn vòng poll Python (mỗi vòng phải spawn một tiến trình ``dms``).
    """
    proc = native.island_watch(
        source, activity_id, int(duration * 1000),
    )
    if proc is None or proc.stdout is None:
        return None

    try:
        # Chờ watcher xác nhận đã thấy activity. Nếu không, quay về Python.
        deadline = time.monotonic() + NATIVE_READY_TIMEOUT_SEC
        ready = False
        while not ready:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                readable, _, _ = select.select([proc.stdout], [], [], remaining)
            except (OSError, ValueError):
                break
            if not readable:
                break
            line = proc.stdout.readline()
            if not line:
                break
            try:
                event = json.loads(line)
            except (TypeError, ValueError):
                continue
            if isinstance(event, dict) and event.get("type") == "ready":
                ready = True
                continue
            action_event = _parse_event(line)
            if action_event is not None:
                if _handle_event(action_event, payload) == "close":
                    _terminate(proc)
                    _remove_activity(source, activity_id)
                    return 0
        if not ready:
            return None

        for line in proc.stdout:
            event = _parse_event(line)
            if event is None:
                continue
            if _handle_event(event, payload) == "close":
                _terminate(proc)
                _remove_activity(source, activity_id)
                return 0
        try:
            return proc.wait(timeout=1) or 0
        except Exception:  # noqa: BLE001
            return 0
    finally:
        _terminate(proc)


def _run_python_watcher(source: str, activity_id: str, duration: float,
                        payload: Dict[str, Any]) -> int:
    """Fallback khi không có helper Rust hoặc helper không khởi động được."""
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
                _remove_activity(source, activity_id)
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

    _remove_activity(source, activity_id)
    return 0


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

    native_status = _run_native_watcher(
        source, activity_id, duration, payload,
    )
    if native_status is not None:
        if native_status == 0:
            return 0
        # Watcher Rust lỗi giữa chừng: nếu island vẫn còn, tiếp tục bằng Python.
        entries = dms.island_list()
        if entries is not None and any(
            isinstance(entry, dict)
            and entry.get("source") == source
            and entry.get("id") == activity_id
            for entry in entries
        ):
            return _run_python_watcher(
                source, activity_id, duration, payload,
            )
        return native_status

    return _run_python_watcher(source, activity_id, duration, payload)


if __name__ == "__main__":
    sys.exit(main())
