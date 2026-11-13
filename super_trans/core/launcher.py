"""
Tích hợp trực tiếp với các tiện ích có sẵn của hệ thống (DMS Launcher / Spotlight, DMS Notepad, wtype)
Không dùng thông báo hay popup OSD rời rạc, mà hòa nhập 100% vào các công cụ sẵn có.
"""

import subprocess
import shutil
import time
import os
from super_trans.core.clipboard import set_clipboard_text
from super_trans.engines.opencode_engine import OpenCodeEngine

def replace_selection_in_place(text: str) -> bool:
    """
    Thay thế trực tiếp đoạn văn bản đang bôi đen bằng bản dịch.
    Không mở bất kỳ cửa sổ hay thông báo nào.
    """
    if not text:
        return False

    # 1. Lưu vào cả CLIPBOARD lẫn PRIMARY selection của Wayland
    set_clipboard_text(text)
    if shutil.which("wl-copy"):
        try:
            p = subprocess.Popen(["wl-copy", "--primary"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text, timeout=2)
        except Exception:
            pass

    # 2. Chờ 60ms để Wayland compositor cập nhật clipboard
    time.sleep(0.06)

    # 3. Giả lập nhấn Ctrl+V để thay thế ngay tại vị trí bôi đen
    if shutil.which("wtype"):
        try:
            subprocess.run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], timeout=2)
            return True
        except Exception:
            pass

    return False

def open_in_dms_notepad(orig: str, analysis: str, src_lang: str, tgt_lang: str) -> bool:
    """
    Mở bài phân tích chuyên sâu OpenCode AI trong tiện ích DMS Notepad có sẵn của hệ thống.
    """
    tmp_path = "/tmp/super_trans_analysis.md"
    content = (
        f"# 🌐 SuperTrans Phân Tích Ngữ Cảnh [{src_lang.upper()} ➔ {tgt_lang.upper()}]\n\n"
        f"### 📌 Văn bản gốc:\n> {orig}\n\n"
        f"────────────────────────────────────────────\n\n"
        f"{analysis}\n"
    )

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        if shutil.which("dms"):
            res = subprocess.run(
                ["dms", "ipc", "call", "notepad", "openFile", tmp_path],
                capture_output=True,
                text=True,
                timeout=3
            )
            return "SUCCESS" in res.stdout
    except Exception:
        pass
    return False

def show_in_launcher(orig: str, trans: str, src_lang: str = "auto",
                     tgt_lang: str = "vi", engine_name: str = "Fast") -> str:
    """
    Hiển thị kết quả dịch trực tiếp trong giao diện Launcher / Spotlight có sẵn của DMS (dms dmenu).
    Người dùng có thể chọn hành động (Sao chép, Thay thế tại chỗ, Phân tích AI).
    """
    src_up = src_lang.upper() if src_lang else "AUTO"
    tgt_up = tgt_lang.upper() if tgt_lang else "VI"

    clean_trans = trans.replace("\n", " ").strip()
    if len(clean_trans) > 100:
        clean_trans = clean_trans[:97] + "..."

    clean_orig = orig.replace("\n", " ").strip()
    if len(clean_orig) > 90:
        clean_orig = clean_orig[:87] + "..."

    # Các mục hiển thị trong DMS Launcher
    items = [
        f"🌟 [Bản dịch] {clean_trans}",
        f"✍️ [Thay thế tại chỗ] Dán đè vào vị trí đang bôi đen",
        f"🧠 [Phân tích AI] Mở phân tích chuyên sâu trong DMS Notepad",
        f"📋 [Bản gốc] {clean_orig}"
    ]
    stdin_content = "\n".join(items) + "\n"

    selected = ""

    # 1. Ưu tiên dùng DMS dmenu (Launcher chính chủ của DMS)
    if shutil.which("dms"):
        cmd = [
            "dms", "dmenu",
            "-p", f"Dịch [{src_up} ➔ {tgt_up}]",
            "--placeholder", "Nhấn Enter để chọn hành động, hoặc Esc để đóng...",
            "-l", str(len(items)),
            "--format", "s"
        ]
        try:
            res = subprocess.run(cmd, input=stdin_content, text=True, capture_output=True, timeout=60)
            if res.returncode == 0:
                selected = res.stdout.strip()
        except Exception:
            pass

    # 2. Fallback sang Fuzzel nếu DMS dmenu không phản hồi
    if not selected and shutil.which("fuzzel"):
        cmd = [
            "fuzzel", "--dmenu",
            "-p", f"Dịch [{src_up} ➔ {tgt_up}] > ",
            "-l", str(len(items)),
            "-w", "50"
        ]
        try:
            res = subprocess.run(cmd, input=stdin_content, text=True, capture_output=True, timeout=60)
            if res.returncode == 0:
                selected = res.stdout.strip()
        except Exception:
            pass

    if not selected:
        return ""

    # Xử lý hành động người dùng chọn
    if selected.startswith("🌟 [Bản dịch]") or selected == trans:
        set_clipboard_text(trans)
        return "copied"
    elif selected.startswith("✍️ [Thay thế tại chỗ]"):
        replace_selection_in_place(trans)
        return "replaced"
    elif selected.startswith("🧠 [Phân tích AI]"):
        # Chạy phân tích OpenCode AI và mở trong DMS Notepad
        ai_engine = OpenCodeEngine()
        analysis, _ = ai_engine.translate(orig, src_lang=src_lang, tgt_lang=tgt_lang)
        open_in_dms_notepad(orig, analysis, src_lang, tgt_lang)
        return "opened_notepad"
    elif selected.startswith("📋 [Bản gốc]"):
        set_clipboard_text(orig)
        return "copied_orig"

    # Mặc định: copy văn bản đã dịch
    set_clipboard_text(trans)
    return "copied"

def prompt_input_via_launcher() -> str:
    """Mở ô nhập liệu nhanh qua DMS Launcher hoặc Fuzzel."""
    if shutil.which("dms"):
        cmd = [
            "dms", "dmenu",
            "--prompt-only",
            "-p", "🌐 Dịch thuật:",
            "--placeholder", "Nhập văn bản tiếng Anh, Pháp, Trung cần dịch..."
        ]
        try:
            res = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    if shutil.which("fuzzel"):
        cmd = [
            "fuzzel", "--dmenu",
            "--prompt-only=🌐 Dịch > ",
            "-l", "0",
            "-w", "45",
            "--placeholder=Nhập văn bản cần dịch..."
        ]
        try:
            res = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return ""
