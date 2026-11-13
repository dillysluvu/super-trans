"""
CLI Entry Point cho SuperTrans
"""

import sys
import argparse
from super_trans.config import load_config
from super_trans.core.detector import resolve_languages
from super_trans.core.clipboard import get_selection_text, set_clipboard_text
from super_trans.core.ocr import capture_and_ocr
from super_trans.core.notifier import display_result
from super_trans.core.launcher import open_in_dms_notepad, prompt_input_via_launcher
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine
from super_trans import __version__

def parse_args():
    parser = argparse.ArgumentParser(
        prog="super-trans",
        description="🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống (Hợp tác Antigravity & OpenCode)"
    )

    parser.add_argument("text", nargs="*", help="Văn bản cần dịch (hoặc để trống để dùng các chế độ phím tắt)")
    parser.add_argument("-s", "--selection", action="store_true", help="Lấy văn bản đang được bôi đen hoặc trong clipboard")
    parser.add_argument("-o", "--ocr", action="store_true", help="Kéo chuột chụp vùng màn hình và nhận diện chữ (OCR)")
    parser.add_argument("-i", "--input", action="store_true", help="Mở hộp thoại nhập liệu nhanh DMS Launcher để gõ văn bản cần dịch")
    parser.add_argument("-r", "--replace", action="store_true", help="Thay thế trực tiếp tại chỗ bằng bản dịch (In-place replace qua wtype)")
    parser.add_argument("-e", "--engine", choices=["fast", "ai"], default=None, help="Bộ máy dịch: 'fast' (tốc độ cao) hoặc 'ai' (OpenCode AI)")
    parser.add_argument("--output", "-m", dest="output_mode",
                        choices=["launcher", "replace", "osd", "dms_toast", "notification", "none"],
                        default=None,
                        help="Hình thức hiển thị: 'launcher' (DMS Spotlight Launcher), 'replace' (Thay thế tại chỗ), 'osd', 'dms_toast'")
    parser.add_argument("--from", dest="from_lang", default=None, help="Mã ngôn ngữ nguồn (ví dụ: en, fr, zh, vi, auto)")
    parser.add_argument("--to", dest="to_lang", default=None, help="Mã ngôn ngữ đích (mặc định: vi)")
    parser.add_argument("--no-copy", action="store_true", help="Không tự động copy kết quả vào clipboard")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    return parser.parse_args()

def main() -> int:
    args = parse_args()
    config = load_config()

    input_text = ""

    # 1. Thu thập văn bản cần dịch theo độ ưu tiên
    if args.ocr:
        ocr_lang = config.get("ocr_lang", "eng+fra+chi_sim+vie")
        input_text = capture_and_ocr(lang=ocr_lang)
        if not input_text:
            return 0  # Hủy chọn hoặc không nhận diện được chữ
    elif args.input:
        input_text = prompt_input_via_launcher()
        if not input_text:
            return 0  # Người dùng hủy nhập
    elif args.selection or args.replace:
        input_text = get_selection_text()
        if not input_text:
            return 1
    elif args.text:
        input_text = " ".join(args.text).strip()
    elif not sys.stdin.isatty():
        # Đọc dữ liệu từ pipe (ví dụ: echo "hello" | super-trans)
        input_text = sys.stdin.read().strip()

    if not input_text:
        # Nếu chạy không tham số, mở input prompt qua DMS Launcher
        input_text = prompt_input_via_launcher()
        if not input_text:
            return 0

    # 2. Xác định ngôn ngữ nguồn & đích tự động (ưu tiên dịch sang Tiếng Việt cho Anh, Pháp, Trung)
    src_lang, tgt_lang = resolve_languages(
        input_text,
        source_lang=args.from_lang,
        target_lang=args.to_lang,
        primary_target=config.get("primary_target_lang", "vi"),
        secondary_target=config.get("secondary_target_lang", "en")
    )

    # 3. Lựa chọn bộ máy dịch
    engine_choice = args.engine or config.get("default_engine", "fast")

    translated = ""
    detected_src = src_lang
    active_engine_name = "Fast"

    if engine_choice == "ai":
        active_engine_name = "OpenCode AI"
        ai_engine = OpenCodeEngine(model=config.get("ai_model", "opencode/deepseek-v4.1-flash-free"))
        try:
            translated, detected_src = ai_engine.translate(input_text, src_lang=src_lang, tgt_lang=tgt_lang)
            # Nếu là AI mode và cấu hình mở trong DMS Notepad
            if config.get("show_popup_on_ai", True):
                open_in_dms_notepad(input_text, translated, detected_src, tgt_lang)
        except Exception as e:
            fallback_engine = FastEngine()
            translated, detected_src = fallback_engine.translate(input_text, src_lang=src_lang, tgt_lang=tgt_lang)
            active_engine_name = "Fast (AI Fallback)"
    else:
        fast_engine = FastEngine()
        try:
            translated, detected_src = fast_engine.translate(input_text, src_lang=src_lang, tgt_lang=tgt_lang)
            active_engine_name = "Fast"
        except Exception as e:
            print(f"Lỗi: {e}", file=sys.stderr)
            return 1

    # 4. Sao chép kết quả vào clipboard nếu được bật
    if not args.no_copy and config.get("auto_copy_to_clipboard", True):
        set_clipboard_text(translated)

    # 5. Hiển thị kết quả bằng các tiện ích sẵn có của hệ thống
    # Nếu có cờ --replace, ép mode = 'replace'
    if args.replace:
        out_mode = "replace"
    else:
        out_mode = args.output_mode or config.get("output_mode", "launcher")

    if out_mode != "none":
        timeout_ms = config.get("notification_timeout_ms", 6000)
        display_result(
            original=input_text,
            translated=translated,
            src_lang=detected_src,
            tgt_lang=tgt_lang,
            engine_name=active_engine_name,
            mode=out_mode,
            timeout_ms=timeout_ms
        )

    # 6. In ra stdout cho terminal / script
    print(translated)
    return 0

if __name__ == "__main__":
    sys.exit(main())
