"""
Hiển thị kết quả dịch trên Dynamic Island của DMS.

Giao diện island được tối giản thành hai dòng:

    gốc : nghĩa
    engine · ngữ cảnh

Phần chi tiết (bản dịch đầy đủ) nằm trong body khi người dùng mở rộng island.
Các nút "Sao chép" / "Phân tích" được xử lý bởi một tiến trình nền nhỏ
(``super_trans.core.island_watch``) để CLI có thể thoát ngay sau khi publish.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from super_trans.core import dms, presentation

DEFAULT_DURATION_MS = 10000
MIN_DURATION_MS = 2000
MAX_DURATION_MS = 60000
SOURCE_PREFIX = "supertrans"


def _source() -> str:
    """Source duy nhất cho mỗi lần publish, tránh lẫn action giữa các tiến trình."""
    return f"{SOURCE_PREFIX}-{os.getpid()}-{int(time.time() * 1000)}"


def _activity_id() -> str:
    return f"result-{int(time.time() * 1000)}-{os.getpid()}"


def _focused_output() -> str:
    """Tên output đang focus trên Niri (rỗng nếu không xác định)."""
    if not shutil.which("niri"):
        return ""
    try:
        result = subprocess.run(
            ["niri", "msg", "--json", "focused-output"],
            capture_output=True, text=True, timeout=1.0,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        data = json.loads(result.stdout)
        return str(data.get("name") or "")
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def _clamp_duration(timeout_ms: int) -> int:
    try:
        duration = int(timeout_ms)
    except (TypeError, ValueError):
        duration = DEFAULT_DURATION_MS
    return max(MIN_DURATION_MS, min(MAX_DURATION_MS, duration))


def build_payload(original: str, translated: str, src_lang: str = "auto",
                  tgt_lang: str = "vi", engine_name: str = "Fast",
                  context: str = "", timeout_ms: int = DEFAULT_DURATION_MS,
                  screen: str = "") -> Dict[str, Any]:
    """Tạo payload island tối giản, không lặp lại thông tin."""
    title = presentation.compact_pair(original, translated, 240)
    subtitle = presentation.context_line(
        engine_name, context, src_lang, tgt_lang, 160,
    )
    body = (translated or "").strip()

    payload: Dict[str, Any] = {
        "title": title,
        "subtitle": subtitle,
        "body": body,
        "icon": "translate",
        "duration": _clamp_duration(timeout_ms),
        "position": "center",
        "priorityClass": "high",
        "preemption": "higher",
        "dismissible": True,
        "announce": True,
        "actions": [
            {"id": "copy", "label": "Sao chép", "role": "primary"},
            {"id": "analyze", "label": "Phân tích", "role": "secondary"},
        ],
    }
    if screen:
        payload["screen"] = screen
    return payload


def _spawn_watcher(payload: Dict[str, Any]) -> bool:
    """Chạy tiến trình nền xử lý action của island."""
    python = sys.executable or shutil.which("python3")
    if not python:
        return False

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    env = os.environ.copy()
    current_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        project_root + (os.pathsep + current_path if current_path else "")
    )

    proc = None
    try:
        proc = subprocess.Popen(
            [python, "-m", "super_trans.core.island_watch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
            close_fds=True,
            cwd=project_root,
            env=env,
        )
        if proc.stdin is None:
            proc.terminate()
            return False
        proc.stdin.write(json.dumps(payload, ensure_ascii=False))
        proc.stdin.close()
        return True
    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
        if proc is not None and proc.poll() is None:
            proc.terminate()
        return False


def show_in_island(original: str, translated: str, src_lang: str = "auto",
                   tgt_lang: str = "vi", engine_name: str = "Fast",
                   context: Optional[str] = None, analysis: str = "",
                   ai_model: Optional[str] = None, ai_timeout: float = 120.0,
                   timeout_ms: int = DEFAULT_DURATION_MS) -> bool:
    """
    Publish kết quả lên Dynamic Island.

    ``context=None`` nghĩa là tự lấy ngữ cảnh từ analysis; truyền chuỗi rỗng
    để chủ động không hiển thị ngữ cảnh (tránh lặp lại bản dịch).
    Trả False nếu DMS/island không khả dụng để caller fallback sang launcher.
    """
    if not dms.available() or not dms.island_available():
        return False

    if context is None:
        context = presentation.short_context(analysis) if analysis else ""

    source = _source()
    activity_id = _activity_id()
    payload = build_payload(
        original, translated, src_lang, tgt_lang, engine_name,
        context=context, timeout_ms=timeout_ms, screen=_focused_output(),
    )
    if not dms.island_publish(source, activity_id, payload):
        return False

    watcher_started = _spawn_watcher({
        "source": source,
        "id": activity_id,
        "original": original,
        "translated": translated,
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
        "engine": engine_name,
        "analysis": analysis or "",
        "ai_model": ai_model or "",
        "ai_timeout": ai_timeout,
        "duration_ms": payload["duration"],
    })
    if not watcher_started:
        # Không xử lý được nút bấm thì đừng để island "chết"; quay về Launcher.
        dms.island_remove(source, activity_id)
        return False
    return True
