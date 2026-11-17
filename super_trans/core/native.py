"""
Cầu nối tới helper Rust tùy chọn (``super-trans-native``).

Helper xử lý hai phần:
  - chia văn bản dài (CPU-bound) khi dịch tài liệu lớn;
  - IPC trực tiếp tới Quickshell/DMS cho Dynamic Island, tránh spawn ``dms``
    cho mỗi lần publish/open/poll.

Nếu chưa build Rust hoặc helper gặp lỗi, mọi thứ tự động quay về Python/DMS CLI.
"""

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

NATIVE_NAME = "super-trans-native"
MIN_NATIVE_CHARS = 4000

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CANDIDATES = (
    os.path.expanduser("~/.local/lib/super-trans/" + NATIVE_NAME),
    os.path.join(PROJECT_ROOT, "native", "target", "release", NATIVE_NAME),
    os.path.join(PROJECT_ROOT, "native", "target", "debug", NATIVE_NAME),
)


def find_binary() -> Optional[str]:
    """Tìm helper Rust theo thứ tự: biến môi trường, cài đặt, build tại chỗ, PATH."""
    override = os.environ.get("SUPERTRANS_NATIVE_BIN")
    if override and os.path.isfile(override) and os.access(override, os.X_OK):
        return override

    for candidate in _CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return shutil.which(NATIVE_NAME)


def available() -> bool:
    return find_binary() is not None


_CAPABILITY_CACHE: Dict[str, Dict[str, Any]] = {}


def capabilities() -> Dict[str, Any]:
    """Khả năng của helper Rust (cache theo đường dẫn binary)."""
    binary = find_binary()
    if not binary:
        return {}
    if binary in _CAPABILITY_CACHE:
        return _CAPABILITY_CACHE[binary]
    try:
        res = subprocess.run(
            [binary, "capabilities"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        data = json.loads(res.stdout or "{}") if res.returncode == 0 else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    _CAPABILITY_CACHE[binary] = data
    return data


def island_capable() -> bool:
    """Helper có hỗ trợ IPC island trực tiếp hay không."""
    return bool(capabilities().get("island"))


def version() -> str:
    binary = find_binary()
    if not binary:
        return ""
    try:
        res = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def split_text(text: str, limit: int) -> Optional[List[str]]:
    """
    Chia văn bản bằng helper Rust. Trả về None để Python tự xử lý nếu:
      - văn bản ngắn (không đáng để khởi tạo tiến trình),
      - helper chưa được build,
      - helper lỗi hoặc kết quả không khớp nội dung gốc.
    """
    if not text or len(text) < MIN_NATIVE_CHARS:
        return None
    if "\x00" in text:
        return None

    binary = find_binary()
    if not binary:
        return None

    try:
        res = subprocess.run(
            [binary, "chunk", "--limit", str(int(limit))],
            input=text,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

    if res.returncode != 0 or not res.stdout:
        return None

    chunks = [chunk.strip() for chunk in res.stdout.split("\x00") if chunk.strip()]
    if not chunks:
        return None
    if any(len(chunk) > limit for chunk in chunks):
        return None

    # Kiểm tra không mất nội dung (bỏ qua khoảng trắng tại ranh giới).
    if "".join(text.split()) != "".join("".join(chunks).split()):
        return None

    return chunks


def island_publish(source: str, activity_id: str, payload: Dict[str, Any],
                   timeout: float = 3.0) -> Optional[bool]:
    """
    Publish + auto-expand qua IPC trực tiếp của helper Rust.

    Trả ``None`` nếu helper không hỗ trợ (để caller fallback sang DMS CLI),
    ``True``/``False`` nếu helper đã xử lý.
    """
    if not source or not activity_id or not isinstance(payload, dict):
        return False
    if not island_capable():
        return None
    try:
        encoded = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return False

    binary = find_binary()
    if not binary:
        return None
    try:
        res = subprocess.run(
            [binary, "island", "publish", source, activity_id],
            input=encoded,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    output = res.stdout or ""
    if res.returncode != 0 or "PUBLISHED=1" not in output:
        return False
    # Helper luôn thử open sau publish. Nếu vì lý do nào đó chưa mở được,
    # thử thêm một lần để island chắc chắn hiện đầy đủ nội dung.
    if "OPENED=1" not in output:
        island_open(source, activity_id)
    return True


def island_open(source: str, activity_id: str,
                timeout: float = 2.0) -> Optional[bool]:
    """Mở rộng một activity đã publish qua helper Rust."""
    if not source or not activity_id or not island_capable():
        return None
    binary = find_binary()
    if not binary:
        return None
    try:
        res = subprocess.run(
            [binary, "island", "open", source, activity_id],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(
        res.returncode == 0
        and "ISLAND_ACTIVITY_OPENED" in (res.stdout or "")
    )


def island_remove(source: str, activity_id: str,
                  timeout: float = 2.0) -> Optional[bool]:
    """Xóa activity qua helper Rust; None nếu helper không hỗ trợ."""
    if not source or not activity_id or not island_capable():
        return None
    binary = find_binary()
    if not binary:
        return None
    try:
        res = subprocess.run(
            [binary, "island", "remove", source, activity_id],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(
        res.returncode == 0
        and (
            "ISLAND_ACTIVITY_REMOVED" in (res.stdout or "")
            or "ISLAND_ACTIVITY_NOT_FOUND" in (res.stdout or "")
        )
    )


def island_watch(source: str, activity_id: str, duration_ms: int,
                 poll_ms: int = 80) -> Optional[subprocess.Popen]:
    """
    Khởi chạy watcher Rust, trả Popen có stdout phát JSON lines.

    Watcher phát ``{"type":"ready"}`` sau khi thấy activity, sau đó phát
    ``{"type":"action", ...}`` mỗi khi người dùng bấm nút. Trả None nếu helper
    không hỗ trợ để caller dùng vòng poll Python.
    """
    if not source or not activity_id or not island_capable():
        return None
    binary = find_binary()
    if not binary:
        return None
    try:
        return subprocess.Popen(
            [
                binary, "island", "watch", source, activity_id,
                "--duration-ms", str(max(1, int(duration_ms))),
                "--poll-ms", str(max(40, int(poll_ms))),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            close_fds=True,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def status() -> Dict[str, object]:
    """Thông tin cho lệnh --doctor."""
    binary = find_binary()
    caps = capabilities() if binary else {}
    return {
        "available": bool(binary),
        "path": binary or "",
        "version": version(),
        "threshold": MIN_NATIVE_CHARS,
        "island_ipc": bool(caps.get("island")),
        "ipc": str(caps.get("ipc") or ""),
    }
