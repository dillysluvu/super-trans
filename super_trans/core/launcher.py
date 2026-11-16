"""
Tích hợp trực tiếp với các tiện ích có sẵn của hệ thống (DMS Launcher / Spotlight,
DMS Notepad, DMS Clipboard, wtype) — không dùng thông báo hay popup rời rạc.

Mọi tích hợp DMS đều có đường lui an toàn:
  DMS dmenu  -> fuzzel
  DMS paste  -> wtype
  DMS notepad-> xdg-open
"""

import json
import os
import shutil
import subprocess
import time

from super_trans.core import dms, store
from super_trans.core.clipboard import set_clipboard_text, set_primary_text
from super_trans.engines.opencode_engine import OpenCodeEngine

# Các terminal cần Ctrl+Shift+V thay vì Ctrl+V
TERMINAL_APP_IDS = {
    "alacritty", "foot", "ghostty", "kitty", "konsole", "ptyxis",
    "wezterm", "xterm", "gnome-terminal", "org.gnome.console",
    "com.mitchellh.ghostty", "dev.warp.warp", "tmux",
}


def _focused_app_id() -> str:
    """Lấy app_id của cửa sổ đang focus trên Niri (rỗng nếu không xác định)."""
    if not shutil.which("niri"):
        return ""
    try:
        res = subprocess.run(
            ["niri", "msg", "--json", "focused-window"],
            capture_output=True, text=True, timeout=1.0,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return ""
        data = json.loads(res.stdout)
        return str(data.get("app_id") or "").lower()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def _is_terminal(app_id: str) -> bool:
    if not app_id:
        return False
    return any(term in app_id for term in TERMINAL_APP_IDS)


def _send_paste(shift: bool) -> bool:
    """Gửi tổ hợp dán: ưu tiên DMS, sau đó tới wtype."""
    if dms.send_paste(shift=shift):
        return True

    if not shutil.which("wtype"):
        return False

    keys = ["-M", "ctrl"]
    if shift:
        keys.extend(["-M", "shift"])
    keys.extend(["-k", "v"])
    if shift:
        keys.extend(["-m", "shift"])
    keys.extend(["-m", "ctrl"])

    try:
        subprocess.run(["wtype", *keys], timeout=2)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def replace_selection_in_place(text: str, focus_delay: float = 0.0,
                               original: str = None, src_lang: str = "auto",
                               tgt_lang: str = "vi", engine: str = "fast",
                               record: bool = True) -> bool:
    """
    Thay thế trực tiếp đoạn văn bản đang bôi đen bằng bản dịch.
    Không mở bất kỳ cửa sổ hay thông báo nào.

    Khi ``original`` được cung cấp, lưu lại lần thay thế vào SQLite để có thể
    hoàn tác bằng ``super-trans --undo``.
    """
    if not text:
        return False

    # Khi gọi từ DMS Launcher, chờ cửa sổ launcher đóng và trả focus về ứng dụng.
    if focus_delay > 0:
        time.sleep(focus_delay)

    # 1. Đưa bản dịch vào CLIPBOARD (và PRIMARY để middle-click vẫn dùng được)
    set_clipboard_text(text)
    set_primary_text(text)

    # 2. Chờ compositor cập nhật clipboard
    time.sleep(0.12)

    # 3. Dán đè tại vị trí con trỏ (Ctrl+Shift+V trong terminal)
    app_id = _focused_app_id()
    shift = _is_terminal(app_id)
    pasted = _send_paste(shift=shift)

    # 4. Chỉ ghi nhận khi đã dán thành công, để undo không khôi phục nhầm.
    if pasted and record and original:
        store.record_replacement(
            original_text=original,
            translated_text=text,
            app_id=app_id,
            source_lang=src_lang,
            target_lang=tgt_lang,
            engine=engine,
        )

    return pasted


def _send_ctrl_z() -> bool:
    """Gửi Ctrl+Z qua wtype (DMS hiện chưa có lệnh gửi phím tùy ý)."""
    if not shutil.which("wtype"):
        return False
    try:
        res = subprocess.run(
            ["wtype", "-M", "ctrl", "-k", "z", "-m", "ctrl"],
            timeout=2,
        )
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def undo_last_replacement(force: bool = False) -> tuple:
    """
    Hoàn tác lần thay thế gần nhất bằng Ctrl+Z.

    Trả về ``(thành_công, thông_điệp)``. Nếu cửa sổ hiện tại khác cửa sổ đã
    thay thế, từ chối trừ khi ``force=True`` để tránh Ctrl+Z nhầm ứng dụng.
    """
    record = store.last_replacement()
    if not record:
        return False, "Không có lần thay thế nào để hoàn tác."

    current_app = _focused_app_id()
    recorded_app = (record.get("app_id") or "").lower()
    if (
        not force
        and recorded_app
        and current_app
        and recorded_app != current_app
    ):
        return (
            False,
            "Cửa sổ đang focus khác cửa sổ đã thay thế "
            f"({recorded_app} → {current_app}). Dùng --undo --force nếu chắc chắn.",
        )

    # Trong terminal, Ctrl+Z là SIGTSTP (tạm dừng tiến trình), không phải undo.
    # Tuyệt đối không gửi tổ hợp này vào terminal.
    target_app = recorded_app or current_app
    if _is_terminal(target_app):
        set_clipboard_text(record["original_text"])
        return (
            False,
            "Cửa sổ đích là terminal nên không gửi Ctrl+Z (sẽ tạm dừng tiến "
            "trình). Đã sao chép bản gốc vào clipboard — hãy dán thủ công "
            "bằng Ctrl+Shift+V.",
        )

    if not _send_ctrl_z():
        # Không thể gửi phím: ít nhất đưa bản gốc vào clipboard để dán thủ công.
        set_clipboard_text(record["original_text"])
        return (
            False,
            "Không gửi được Ctrl+Z (thiếu wtype?). Đã sao chép bản gốc vào "
            "clipboard — hãy dán thủ công rồi chạy lại nếu cần.",
        )

    store.mark_replacement_undone(record["id"])
    set_clipboard_text(record["original_text"])
    return True, "Đã hoàn tác lần thay thế gần nhất."


def _cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "super-trans")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return "/tmp"
    return path


def open_in_dms_notepad(orig: str, analysis: str, src_lang: str, tgt_lang: str) -> bool:
    """
    Mở bài phân tích chuyên sâu trong tiện ích DMS Notepad có sẵn.
    Nếu DMS Notepad không khả dụng, mở file bằng ứng dụng mặc định (xdg-open).
    """
    src_up = (src_lang or "auto").upper()
    tgt_up = (tgt_lang or "vi").upper()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    filename = time.strftime("super-trans-analysis-%Y%m%d-%H%M%S") + f"-{os.getpid()}.md"
    path = os.path.join(_cache_dir(), filename)

    header = (
        "# 🌐 SuperTrans · Phân tích ngôn ngữ\n\n"
        f"**Chiều dịch:** `{src_up} ➔ {tgt_up}`  \n"
        f"**Thời gian:** {timestamp}\n\n"
    )
    if orig.strip():
        quoted = "\n".join(f"> {line}" for line in orig.strip().splitlines())
        header += f"## 📌 Văn bản gốc\n\n{quoted}\n\n---\n\n"

    content = header + (analysis.strip() or "_Không có nội dung phân tích._") + "\n\n---\n\n*Tạo bởi SuperTrans · OpenCode AI*\n"

    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError:
        return False

    if dms.open_notepad(path):
        return True

    # Fallback: mở bằng ứng dụng mặc định của hệ thống
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except OSError:
            pass

    return False


def _fuzzel_pick(items, prompt: str, placeholder: str = "", lines: int = 0,
                 timeout: float = 90.0):
    """Fallback dmenu qua fuzzel. Trả về (trạng thái, lựa chọn)."""
    if not shutil.which("fuzzel"):
        return dms.DMENU_UNAVAILABLE, ""

    if items is None:
        cmd = ["fuzzel", "--dmenu", f"--prompt-only={prompt}", "-w", "58"]
    else:
        cmd = ["fuzzel", "--dmenu", "-p", prompt, "-l", str(lines), "-w", "58"]
    if placeholder:
        cmd.extend(["--placeholder", placeholder])

    stdin_text = None
    if items is not None:
        stdin_text = "".join(f"{item}\n" for item in items)

    try:
        res = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return dms.DMENU_UNAVAILABLE, ""

    if res.returncode == 0:
        return dms.DMENU_OK, res.stdout.strip()
    if res.returncode == 1:
        return dms.DMENU_CANCELLED, ""
    return dms.DMENU_UNAVAILABLE, ""


def _pick_item(items, prompt: str, placeholder: str = "", lines: int = 0,
               timeout: float = 90.0) -> str:
    """Chọn một mục qua DMS Launcher, chỉ fallback fuzzel khi DMS không khả dụng."""
    status, selected = dms.dmenu(
        items,
        prompt=prompt,
        placeholder=placeholder,
        lines=lines,
        extra_args=["--icon", "translate"],
        timeout=timeout,
    )
    if status == dms.DMENU_OK:
        return selected
    if status == dms.DMENU_CANCELLED:
        return ""

    status, selected = _fuzzel_pick(items, prompt, placeholder, lines, timeout)
    return selected if status == dms.DMENU_OK else ""


def show_in_launcher(orig: str, trans: str, src_lang: str = "auto",
                     tgt_lang: str = "vi", engine_name: str = "Fast",
                     ai_model: str = None, ai_timeout: float = 120.0) -> str:
    """
    Hiển thị kết quả dịch trong DMS Launcher / Spotlight (dms dmenu).
    Người dùng chọn: sao chép, thay thế tại chỗ, hoặc phân tích AI.
    """
    src_up = src_lang.upper() if src_lang else "AUTO"
    tgt_up = tgt_lang.upper() if tgt_lang else "VI"

    clean_trans = trans.replace("\n", " ").strip()
    if len(clean_trans) > 100:
        clean_trans = clean_trans[:97] + "..."

    clean_orig = orig.replace("\n", " ").strip()
    if len(clean_orig) > 90:
        clean_orig = clean_orig[:87] + "..."

    items = [
        f"🌟 [Bản dịch] {clean_trans}",
        "✍️ [Thay thế tại chỗ] Dán đè vào vị trí đang bôi đen",
        "🧠 [Phân tích AI] Mở phân tích chuyên sâu trong DMS Notepad",
        f"📋 [Bản gốc] {clean_orig}",
    ]

    selected = _pick_item(
        items,
        prompt=f"Dịch [{src_up} ➔ {tgt_up}]",
        placeholder="Enter để chọn hành động, Esc để đóng...",
        lines=len(items),
        timeout=90.0,
    )
    if not selected:
        return ""

    if selected.startswith("🌟 [Bản dịch]"):
        set_clipboard_text(trans)
        return "copied"

    if selected.startswith("✍️ [Thay thế tại chỗ]"):
        replace_selection_in_place(
            trans,
            focus_delay=0.35,
            original=orig,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            engine=engine_name,
        )
        return "replaced"

    if selected.startswith("🧠 [Phân tích AI]"):
        dms.toast(
            "🧠 SuperTrans",
            "Đang phân tích bằng OpenCode AI…",
            "",
            "trans",
        )
        try:
            engine = OpenCodeEngine(model=ai_model, timeout=ai_timeout)
            _, analysis, detected_src = engine.analyze(orig, src_lang=src_lang, tgt_lang=tgt_lang)
        except Exception as exc:  # noqa: BLE001 - cần báo lỗi cho mọi trường hợp
            analysis = f"## ⚠️ Không thể phân tích bằng OpenCode AI\n\n```\n{exc}\n```"
            detected_src = src_lang
            dms.toast("⚠️ SuperTrans", str(exc)[:140], "", "trans")

        opened = open_in_dms_notepad(orig, analysis, detected_src, tgt_lang)
        if not opened:
            dms.notify(
                "🌐 SuperTrans - Phân tích AI",
                analysis[:1000],
                timeout_ms=12000,
            )
        return "opened_notepad"

    if selected.startswith("📋 [Bản gốc]"):
        set_clipboard_text(orig)
        return "copied_orig"

    # Người dùng gõ nội dung tùy ý: mặc định sao chép bản dịch
    set_clipboard_text(trans)
    return "copied"


def prompt_input_via_launcher() -> str:
    """Mở ô nhập liệu nhanh qua DMS Launcher, fallback fuzzel khi DMS vắng mặt."""
    status, text = dms.dmenu(
        None,
        prompt="🌐 Dịch thuật:",
        placeholder="Nhập văn bản tiếng Anh, Pháp, Trung cần dịch...",
        extra_args=["--icon", "translate"],
        timeout=120.0,
    )
    if status == dms.DMENU_OK:
        return text
    if status == dms.DMENU_CANCELLED:
        return ""

    status, text = _fuzzel_pick(
        None,
        prompt="🌐 Dịch > ",
        placeholder="Nhập văn bản cần dịch...",
        lines=0,
        timeout=120.0,
    )
    return text if status == dms.DMENU_OK else ""
