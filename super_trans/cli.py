"""
CLI Entry Point cho SuperTrans
"""

import argparse
import sys
from typing import Optional

from super_trans import __version__
from super_trans.config import load_config
from super_trans.core.clipboard import get_selection_text, set_clipboard_text
from super_trans.core.detector import resolve_languages
from super_trans.core.launcher import open_in_dms_notepad, prompt_input_via_launcher
from super_trans.core.notifier import display_result
from super_trans.core.ocr import capture_and_ocr
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine


def parse_args():
    parser = argparse.ArgumentParser(
        prog="super-trans",
        description="🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống (Hợp tác Antigravity & OpenCode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ví dụ:\n"
            "  trans \"Thank you very much\"\n"
            "  trans -e ai \"塞翁失马\"\n"
            "  trans --selection --output launcher\n"
            "  trans --ocr\n"
            "  echo \"Artificial Intelligence\" | trans\n"
        ),
    )

    parser.add_argument("text", nargs="*", help="Văn bản cần dịch (hoặc để trống để dùng các chế độ phím tắt)")
    parser.add_argument("-s", "--selection", action="store_true", help="Lấy văn bản đang được bôi đen hoặc trong clipboard")
    parser.add_argument("-o", "--ocr", action="store_true", help="Kéo chuột chụp vùng màn hình và nhận diện chữ (OCR)")
    parser.add_argument("--ocr-lang", default=None, help="Ghi đè ngôn ngữ OCR, ví dụ: eng+fra+chi_sim+vie")
    parser.add_argument("-i", "--input", action="store_true", help="Mở hộp thoại nhập liệu nhanh DMS Launcher để gõ văn bản cần dịch")
    parser.add_argument("-r", "--replace", action="store_true", help="Thay thế trực tiếp tại chỗ bằng bản dịch (In-place replace qua DMS/wtype)")
    parser.add_argument("-e", "--engine", choices=["fast", "ai"], default=None, help="Bộ máy dịch: 'fast' (tốc độ cao) hoặc 'ai' (OpenCode AI)")
    parser.add_argument("--output", "-m", dest="output_mode",
                        choices=["launcher", "replace", "osd", "dms_toast", "notification", "none"],
                        default=None,
                        help="Hình thức hiển thị: 'launcher' (DMS Spotlight), 'replace' (Thay thế tại chỗ), 'osd', 'dms_toast', 'notification', 'none'")
    parser.add_argument("--from", dest="from_lang", default=None, help="Mã ngôn ngữ nguồn (ví dụ: en, fr, zh, vi, auto)")
    parser.add_argument("--to", dest="to_lang", default=None, help="Mã ngôn ngữ đích (mặc định: vi)")
    parser.add_argument("--no-copy", action="store_true", help="Không tự động copy kết quả vào clipboard")
    parser.add_argument("--no-popup", action="store_true", help="Không mở DMS Notepad khi dùng engine AI")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    return parser.parse_args()


def _collect_input(args, config) -> Optional[str]:
    """
    Thu thập văn bản cần dịch.
    Trả về None nếu có lỗi không thể tiếp tục, chuỗi rỗng nếu người dùng hủy.
    """
    if args.ocr:
        ocr_lang = args.ocr_lang or config.get("ocr_lang", "eng+fra+chi_sim+vie")
        try:
            return capture_and_ocr(lang=ocr_lang)
        except RuntimeError as exc:
            print(f"❌ Lỗi OCR: {exc}", file=sys.stderr)
            return None

    if args.input:
        return prompt_input_via_launcher()

    if args.selection or args.replace:
        selected = get_selection_text()
        if not selected:
            print(
                "⚠ Không tìm thấy văn bản đang bôi đen (PRIMARY selection) hoặc trong clipboard.",
                file=sys.stderr,
            )
        return selected

    if args.text:
        return " ".join(args.text).strip()

    if not sys.stdin.isatty():
        # Đọc dữ liệu từ pipe (ví dụ: echo "hello" | super-trans)
        return sys.stdin.read().strip()

    # Chạy không tham số: mở ô nhập liệu qua DMS Launcher
    return prompt_input_via_launcher()


def _translate_with_ai(input_text: str, src_lang: str, tgt_lang: str,
                      config, wants_notepad: bool):
    """Dịch bằng OpenCode AI, tự động fallback sang FastEngine khi lỗi."""
    engine = OpenCodeEngine(
        model=config.get("ai_model", "opencode/deepseek-v4.1-flash-free"),
        timeout=config.get("ai_timeout_sec", 120),
    )
    try:
        if wants_notepad:
            translated, analysis, detected_src = engine.analyze(
                input_text, src_lang=src_lang, tgt_lang=tgt_lang
            )
        else:
            translated, detected_src = engine.translate(
                input_text, src_lang=src_lang, tgt_lang=tgt_lang
            )
            analysis = ""
        return translated, analysis, detected_src, "OpenCode AI"
    except Exception as exc:  # noqa: BLE001 - fallback cho mọi lỗi của engine AI
        print(f"⚠ OpenCode AI lỗi: {exc}", file=sys.stderr)
        print("→ Tự động chuyển sang FastEngine.", file=sys.stderr)
        translated, detected_src = FastEngine().translate(
            input_text, src_lang=src_lang, tgt_lang=tgt_lang
        )
        return translated, "", detected_src, "Fast (AI fallback)"


def main() -> int:
    args = parse_args()
    config = load_config()

    # 1. Thu thập văn bản cần dịch
    input_text = _collect_input(args, config)
    if input_text is None:
        return 1
    if not input_text:
        return 0  # Người dùng hủy chọn/nhập

    # 2. Xác định ngôn ngữ nguồn & đích (ưu tiên dịch sang Tiếng Việt)
    src_lang, tgt_lang = resolve_languages(
        input_text,
        source_lang=args.from_lang,
        target_lang=args.to_lang,
        primary_target=config.get("primary_target_lang", "vi"),
        secondary_target=config.get("secondary_target_lang", "en"),
    )

    # 3. Xác định hình thức hiển thị trước khi dịch (để chọn chế độ AI phù hợp)
    out_mode = "replace" if args.replace else (
        args.output_mode or config.get("output_mode", "launcher")
    )
    engine_choice = args.engine or config.get("default_engine", "fast")

    wants_notepad = (
        engine_choice == "ai"
        and not args.no_popup
        and config.get("show_popup_on_ai", True)
        and args.output_mode is None
        and out_mode != "replace"
    )

    # 4. Dịch
    analysis = ""
    if engine_choice == "ai":
        try:
            translated, analysis, detected_src, active_engine_name = _translate_with_ai(
                input_text, src_lang, tgt_lang, config, wants_notepad
            )
        except Exception as exc:  # FastEngine fallback cũng thất bại
            print(f"❌ Lỗi dịch: {exc}", file=sys.stderr)
            return 1

        if wants_notepad and analysis:
            notepad_opened = open_in_dms_notepad(
                input_text, analysis, detected_src, tgt_lang
            )
            # Không mở thêm Launcher khi DMS Notepad đã hiển thị đầy đủ kết quả
            if notepad_opened and args.output_mode is None and out_mode == "launcher":
                out_mode = "none"
    else:
        try:
            translated, detected_src = FastEngine().translate(
                input_text, src_lang=src_lang, tgt_lang=tgt_lang
            )
            active_engine_name = "Fast"
        except Exception as exc:
            print(f"❌ Lỗi dịch: {exc}", file=sys.stderr)
            return 1

    # 5. Sao chép kết quả vào clipboard nếu được bật
    if not args.no_copy and config.get("auto_copy_to_clipboard", True):
        set_clipboard_text(translated)

    # 6. Hiển thị kết quả bằng các tiện ích sẵn có của hệ thống
    display_ok = True
    if out_mode != "none":
        timeout_ms = config.get("notification_timeout_ms", 6000)
        display_ok = display_result(
            original=input_text,
            translated=translated,
            src_lang=detected_src,
            tgt_lang=tgt_lang,
            engine_name=active_engine_name,
            mode=out_mode,
            timeout_ms=timeout_ms,
            ai_model=config.get("ai_model"),
            ai_timeout=config.get("ai_timeout_sec", 120),
        )

    # 7. In ra stdout cho terminal / script
    try:
        print(translated)
    except BrokenPipeError:
        return 0

    if out_mode == "replace" and not display_ok:
        print("⚠ Không thể thay thế tại chỗ (thiếu DMS Clipboard/wtype?).", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
