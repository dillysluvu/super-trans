"""
Lớp tích hợp DMS (DankMaterialShell) dùng chung.

Tập trung toàn bộ lời gọi CLI `dms` tại đây để các module khác không phụ thuộc
trực tiếp vào cú pháp IPC/CLI của DMS. Mọi hàm đều an toàn khi DMS không cài đặt
hoặc DMS shell không chạy: chúng trả về trạng thái thất bại thay vì ném lỗi.
"""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Trạng thái trả về của dmenu()
DMENU_OK = "ok"
DMENU_CANCELLED = "cancelled"
DMENU_UNAVAILABLE = "unavailable"


def dms_bin() -> Optional[str]:
    """Đường dẫn tới CLI dms, hoặc None nếu chưa cài đặt."""
    return shutil.which("dms")


def available() -> bool:
    """Kiểm tra DMS CLI có sẵn trên hệ thống hay không."""
    return dms_bin() is not None


def _run(args: Sequence[str], input_text: Optional[str] = None,
         timeout: float = 3.0) -> Optional[subprocess.CompletedProcess]:
    """Chạy một lệnh con của dms, trả về None nếu không thể thực thi."""
    exe = dms_bin()
    if not exe:
        return None

    try:
        return subprocess.run(
            [exe, *args],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=[exe, *args], returncode=124, stdout="", stderr="timeout"
        )
    except OSError:
        return None


def dmenu(items: Optional[Sequence[str]], prompt: str, placeholder: str = "",
          lines: int = 0, extra_args: Optional[Sequence[str]] = None,
          timeout: float = 90.0) -> Tuple[str, str]:
    """
    Mở DMS Launcher / Spotlight ở chế độ dmenu.

    - items=None: chế độ ô nhập liệu tự do (--prompt-only).
    - Trả về (trạng thái, lựa chọn):
        "ok"          -> người dùng đã xác nhận
        "cancelled"   -> người dùng nhấn Esc / đóng cửa sổ
        "unavailable" -> DMS không có hoặc shell không phản hồi
    """
    args = ["dmenu", "-p", prompt, "--format", "s"]
    if placeholder:
        args.extend(["--placeholder", placeholder])
    if lines > 0:
        args.extend(["-l", str(lines)])
    if items is None:
        args.append("--prompt-only")
    if extra_args:
        args.extend(extra_args)

    stdin_text = None
    if items is not None:
        stdin_text = "".join(f"{item}\n" for item in items)

    result = _run(args, input_text=stdin_text, timeout=timeout)
    if result is None:
        return DMENU_UNAVAILABLE, ""

    if result.returncode == 0:
        return DMENU_OK, result.stdout.strip()
    if result.returncode in (1, 124):
        error_text = (result.stderr or "").lower()
        # Lỗi cú pháp/flag không hỗ trợ (khác với người dùng nhấn Esc)
        if any(marker in error_text for marker in ("unknown flag", "invalid argument", "usage:")):
            return DMENU_UNAVAILABLE, ""
        # 1 = người dùng hủy; 124 = hết thời gian chờ (coi như hủy)
        return DMENU_CANCELLED, ""
    return DMENU_UNAVAILABLE, ""


def toast(message: str, details: str = "", command: str = "",
          category: str = "trans", timeout: float = 2.0) -> bool:
    """Hiển thị toast trên Dynamic Island của DMS."""
    result = _run(
        ["ipc", "call", "toast", "infoWith", message, details, command, category],
        timeout=timeout,
    )
    return bool(result and result.returncode == 0)


def _json_result(args: Sequence[str],
                 timeout: float = 3.0) -> Optional[Any]:
    """Chạy lệnh IPC trả JSON, trả None nếu lỗi hoặc output không hợp lệ."""
    result = _run(args, timeout=timeout)
    if not result or result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "")
    except (TypeError, ValueError):
        return None


def island_available() -> bool:
    """Kiểm tra Dynamic Island của DMS có sẵn và bật activity hay không."""
    data = _json_result(["ipc", "call", "islandActivity", "availability"])
    if not isinstance(data, dict) or not data.get("islandPresent"):
        return False
    return bool(data.get("activitiesAvailable", True))


def island_publish(source: str, activity_id: str, payload: Dict[str, Any],
                   timeout: float = 3.0) -> bool:
    """Đăng một activity lên Dynamic Island; payload gửi qua stdin."""
    if not source or not activity_id or not isinstance(payload, dict):
        return False
    try:
        encoded = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return False

    result = _run(
        [
            "ipc", "call", "islandActivity", "publish",
            source, activity_id, "-",
        ],
        input_text=encoded,
        timeout=timeout,
    )
    return bool(
        result
        and result.returncode == 0
        and "ISLAND_ACTIVITY_PUBLISHED" in (result.stdout or "")
    )


def island_remove(source: str, activity_id: str,
                  timeout: float = 2.0) -> bool:
    """Xóa activity khỏi Dynamic Island."""
    if not source or not activity_id:
        return False
    result = _run(
        ["ipc", "call", "islandActivity", "remove", source, activity_id],
        timeout=timeout,
    )
    return bool(
        result
        and result.returncode == 0
        and "ISLAND_ACTIVITY_REMOVED" in (result.stdout or "")
    )


def island_list(timeout: float = 2.0) -> Optional[List[Dict[str, Any]]]:
    """Liệt kê activity đang hiển thị; None nếu không đọc được."""
    data = _json_result(["ipc", "call", "islandActivity", "list"], timeout=timeout)
    return data if isinstance(data, list) else None


def island_poll_actions(source: str,
                        timeout: float = 2.0) -> List[Dict[str, Any]]:
    """Lấy các action người dùng vừa bấm trên island của một source."""
    if not source:
        return []
    data = _json_result(
        ["ipc", "call", "islandActivity", "pollActions", source],
        timeout=timeout,
    )
    return data if isinstance(data, list) else []


def notify(title: str, body: str, timeout_ms: int = 6000,
           icon: str = "accessories-dictionary", timeout: float = 3.0) -> bool:
    """Gửi thông báo desktop qua DMS (đồng bộ giao diện với hệ thống)."""
    result = _run(
        [
            "notify",
            "-a", "SuperTrans",
            "-i", icon,
            "-t", str(timeout_ms),
            title,
            body,
        ],
        timeout=timeout,
    )
    return bool(result and result.returncode == 0)


def copy_text(text: str) -> bool:
    """Sao chép văn bản qua DMS Clipboard Manager (không cần shell đang chạy)."""
    if not text:
        return False
    result = _run(["clipboard", "copy"], input_text=text, timeout=4.0)
    return bool(result and result.returncode == 0)


def send_paste(shift: bool = False) -> bool:
    """Giả lập Ctrl+V (hoặc Ctrl+Shift+V) qua virtual keyboard của DMS."""
    args = ["clipboard", "send-paste"]
    if shift:
        args.append("--shift")
    result = _run(args, timeout=2.0)
    return bool(result and result.returncode == 0)


def open_notepad(path: str) -> bool:
    """Mở một file Markdown trong DMS Notepad."""
    if not path:
        return False
    result = _run(
        ["ipc", "call", "notepad", "openFile", path],
        timeout=4.0,
    )
    if not result or result.returncode != 0:
        return False
    # DMS trả về NOTEPAD_OPEN_FILE_SUCCESS hoặc NOTEPAD_OPEN_FILE_FAILED.
    output = (result.stdout or "").upper()
    return "NOTEPAD_OPEN_FILE_SUCCESS" in output
