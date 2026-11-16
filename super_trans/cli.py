"""
CLI Entry Point cho SuperTrans
"""

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from super_trans import __version__
from super_trans.config import CONFIG_FILE, load_config
from super_trans.core import dms, native, store
from super_trans.core.clipboard import (
    SOURCE_PRIMARY,
    get_clipboard_text,
    get_selection,
    set_clipboard_text,
)
from super_trans.core.detector import resolve_languages
from super_trans.core.launcher import (
    open_in_dms_notepad,
    prompt_input_via_launcher,
    undo_last_replacement,
)
from super_trans.core.notifier import display_result
from super_trans.core.ocr import (
    capture_and_ocr,
    get_available_ocr_langs,
    missing_ocr_dependencies,
)
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine


@dataclass
class CollectedInput:
    text: str
    source: str = ""


def _psm_type(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("PSM phải là số nguyên từ 0 đến 13")
    if not 0 <= parsed <= 13:
        raise argparse.ArgumentTypeError("PSM phải nằm trong khoảng 0–13")
    return parsed


def parse_args():
    parser = argparse.ArgumentParser(
        prog="super-trans",
        description="🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống (Hợp tác Antigravity & OpenCode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ví dụ:\n"
            "  trans \"Thank you very much\"\n"
            "  trans -e ai \"塞翁失马\"\n"
            "  trans --selection --output island\n"
            "  trans --selection --output launcher\n"
            "  trans --replace            # Chỉ dùng vùng bôi đen PRIMARY\n"
            "  trans --replace --clipboard  # Cho phép thay thế từ clipboard\n"
            "  trans --ocr\n"
            "  trans --ocr-file screenshot.png\n"
            "  echo \"Artificial Intelligence\" | trans\n"
            "  trans --history 10\n"
            "  trans --search \"thank you\"\n"
            "  trans --undo\n"
            "  trans --doctor\n"
        ),
    )

    parser.add_argument("text", nargs="*", help="Văn bản cần dịch (hoặc để trống để dùng các chế độ phím tắt)")
    parser.add_argument("-s", "--selection", action="store_true", help="Lấy văn bản đang được bôi đen hoặc trong clipboard")
    parser.add_argument("--clipboard", "--from-clipboard", action="store_true",
                        help="Dùng clipboard làm nguồn (bắt buộc nếu muốn --replace từ clipboard)")

    ocr_group = parser.add_mutually_exclusive_group()
    ocr_group.add_argument("-o", "--ocr", action="store_true",
                           help="Kéo chuột chụp vùng màn hình và nhận diện chữ (OCR)")
    ocr_group.add_argument("--ocr-file", metavar="PATH",
                           help="OCR một file ảnh có sẵn thay vì chụp màn hình")
    ocr_group.add_argument("--ocr-clipboard", action="store_true",
                           help="OCR ảnh đang có trong clipboard")

    parser.add_argument("--ocr-lang", default=None, help="Ghi đè ngôn ngữ OCR, ví dụ: eng+fra+chi_sim+vie")
    parser.add_argument("--ocr-psm", type=_psm_type, default=None,
                        help="Page Segmentation Mode của Tesseract (0-13, mặc định 3)")
    parser.add_argument("--ocr-preprocess", action=argparse.BooleanOptionalAction,
                        default=None,
                        help="Bật/tắt tăng cường ảnh trước khi OCR (mặc định theo cấu hình)")

    parser.add_argument("-i", "--input", action="store_true", help="Mở hộp thoại nhập liệu nhanh (DMS Launcher/fuzzel) để gõ văn bản cần dịch")
    parser.add_argument("-r", "--replace", action="store_true", help="Thay thế trực tiếp tại chỗ bằng bản dịch (In-place replace qua DMS/wtype)")
    parser.add_argument("-e", "--engine", choices=["fast", "ai"], default=None, help="Bộ máy dịch: 'fast' (tốc độ cao) hoặc 'ai' (OpenCode AI)")
    parser.add_argument("--output", "-m", dest="output_mode",
                        choices=["island", "launcher", "replace", "osd", "dms_toast", "notification", "none"],
                        default=None,
                        help="Hình thức hiển thị: 'island' (Dynamic Island tối giản), 'launcher' (DMS Spotlight), 'replace' (Thay thế tại chỗ), 'osd', 'dms_toast', 'notification', 'none'")
    parser.add_argument("--from", dest="from_lang", default=None, help="Mã ngôn ngữ nguồn (ví dụ: en, fr, zh, vi, auto)")
    parser.add_argument("--to", dest="to_lang", default=None, help="Mã ngôn ngữ đích (mặc định: vi)")
    parser.add_argument("--no-copy", action="store_true", help="Không tự động copy kết quả vào clipboard")
    parser.add_argument("--no-popup", action="store_true", help="Không mở DMS Notepad khi dùng engine AI")

    cache_group = parser.add_argument_group("Cache & lịch sử")
    cache_group.add_argument("--no-cache", action="store_true",
                             help="Không đọc/ghi cache SQLite cho lần dịch này")
    cache_group.add_argument("--refresh", action="store_true",
                             help="Bỏ qua cache, buộc dịch lại rồi cập nhật cache")
    cache_group.add_argument("--history", nargs="?", const=15, type=int, metavar="N",
                             help="Xem N bản dịch gần nhất (mặc định 15)")
    cache_group.add_argument("--search", metavar="TỪ",
                             help="Tìm trong lịch sử dịch")
    cache_group.add_argument("--stats", action="store_true",
                             help="Thống kê cache/lịch sử")
    cache_group.add_argument("--clear-history", action="store_true",
                             help="Xóa toàn bộ lịch sử và cache (cần --yes khi không tương tác)")
    cache_group.add_argument("--yes", action="store_true",
                             help="Xác nhận xóa mà không hỏi lại")

    parser.add_argument("--undo", action="store_true",
                        help="Hoàn tác lần thay thế tại chỗ gần nhất bằng Ctrl+Z")
    parser.add_argument("--force", action="store_true",
                        help="Cho phép undo dù cửa sổ đang focus khác cửa sổ đã thay thế")
    parser.add_argument("--doctor", action="store_true",
                        help="Kiểm tra phụ thuộc, cache, OCR và helper Rust")
    parser.add_argument("--verbose", action="store_true",
                        help="In thêm thông tin chẩn đoán ra stderr")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    return parser.parse_args()


def _collect_input(args, config) -> Optional[CollectedInput]:
    """
    Thu thập văn bản cần dịch.
    Trả về None nếu có lỗi không thể tiếp tục, hoặc CollectedInput rỗng nếu hủy.
    """
    if args.ocr or args.ocr_file or args.ocr_clipboard:
        preprocess = (
            config.get("ocr_preprocess", True)
            if args.ocr_preprocess is None
            else args.ocr_preprocess
        )
        psm = (
            config.get("ocr_psm", 3)
            if args.ocr_psm is None
            else args.ocr_psm
        )
        ocr_lang = args.ocr_lang or config.get("ocr_lang", "eng+fra+chi_sim+vie")
        try:
            text = capture_and_ocr(
                lang=ocr_lang,
                preprocess=bool(preprocess),
                image_path=args.ocr_file,
                from_clipboard=args.ocr_clipboard,
                psm=int(psm),
            )
        except RuntimeError as exc:
            print(f"❌ Lỗi OCR: {exc}", file=sys.stderr)
            return None
        return CollectedInput(text, "ocr")

    if args.input:
        return CollectedInput(prompt_input_via_launcher(), "launcher")

    if args.clipboard:
        text = get_clipboard_text()
        if not text:
            print("⚠ Clipboard đang trống.", file=sys.stderr)
        return CollectedInput(text, "clipboard")

    if args.selection or args.replace:
        # --replace chỉ đọc PRIMARY để tránh dán đè bằng clipboard cũ.
        selection = get_selection(prefer_clipboard=not args.replace)
        if not selection.text:
            if args.replace:
                print(
                    "⚠ Không tìm thấy vùng văn bản đang bôi đen (PRIMARY). "
                    "Để thay thế từ clipboard, dùng: trans --replace --clipboard",
                    file=sys.stderr,
                )
            else:
                print(
                    "⚠ Không tìm thấy văn bản đang bôi đen (PRIMARY) hoặc trong clipboard.",
                    file=sys.stderr,
                )
            return CollectedInput("", selection.source)

        if args.replace and selection.source != SOURCE_PRIMARY:
            print(
                "⚠ --replace cần vùng bôi đen thật (PRIMARY). "
                "Thêm --clipboard nếu chắc chắn muốn dùng clipboard.",
                file=sys.stderr,
            )
            return None

        return CollectedInput(selection.text, selection.source)

    if args.text:
        return CollectedInput(" ".join(args.text).strip(), "text")

    if not sys.stdin.isatty():
        # Đọc dữ liệu từ pipe (ví dụ: echo "hello" | super-trans)
        return CollectedInput(sys.stdin.read().strip(), "pipe")

    # Chạy không tham số: mở ô nhập liệu qua DMS Launcher
    return CollectedInput(prompt_input_via_launcher(), "launcher")


def _translate_with_ai(input_text: str, src_lang: str, tgt_lang: str,
                       config, wants_notepad: bool,
                       want_analysis: bool = False):
    """Dịch bằng OpenCode AI, tự động fallback sang FastEngine khi lỗi."""
    engine = OpenCodeEngine(
        model=config.get("ai_model", "opencode/deepseek-v4.1-flash-free"),
        timeout=config.get("ai_timeout_sec", 120),
    )
    try:
        if wants_notepad or want_analysis:
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


def _one_line(text: str, limit: int = 0) -> str:
    text = " ".join((text or "").split())
    if limit and len(text) > limit:
        return text[: max(1, limit - 1)] + "…"
    return text


def _record_langs(record) -> Tuple[str, str]:
    src = record.get("detected_lang") or record.get("source_lang") or "auto"
    tgt = record.get("target_lang") or "vi"
    return src.upper(), tgt.upper()


def _engine_label(engine: str) -> str:
    engine = engine or "fast"
    return "OpenCode AI" if engine.startswith("ai:") else engine


def _print_history(records, title: str) -> int:
    if not records:
        print(f"📭 {title}: chưa có bản dịch nào.")
        return 0

    print(f"📚 {title} ({len(records)} mục)")
    for record in records:
        src, tgt = _record_langs(record)
        try:
            when = datetime.fromtimestamp(int(record["last_used_at"])).strftime("%d/%m %H:%M")
        except (ValueError, OSError, TypeError):
            when = "?"
        uses = int(record.get("use_count") or 1)
        use_text = f" · dùng {uses} lần" if uses > 1 else ""
        print(
            f"  #{record['id']} · {when} · {src}→{tgt} · "
            f"{_engine_label(record.get('engine', ''))}{use_text}"
        )
        print(f"     {_one_line(record.get('source_text', ''), 120)}")
        print(f"  →  {_one_line(record.get('translated_text', ''), 160)}")
    return 0


def _cmd_history(args) -> int:
    limit = args.history if args.history and args.history > 0 else 15
    return _print_history(store.recent(limit), f"Lịch sử dịch (tối đa {limit} mục)")


def _cmd_search(args) -> int:
    return _print_history(store.search(args.search, 20), f"Kết quả tìm: {args.search!r}")


def _cmd_stats(config) -> int:
    data = store.stats()
    print("📊 SuperTrans · Thống kê")
    print(f"  Database : {data['path']}")
    if data.get("error"):
        print(f"  ⚠ Lỗi DB : {data['error']}")
    size_kb = (data.get("size_bytes") or 0) / 1024.0
    print(f"  Dung lượng: {size_kb:.1f} KB")
    print(f"  Bản dịch  : {data.get('translations', 0)}")
    print(f"  Thay thế  : {data.get('replacements', 0)} (đã hoàn tác: {data.get('undone', 0)})")

    if data.get("newest"):
        try:
            newest = datetime.fromtimestamp(int(data["newest"])).strftime("%d/%m/%Y %H:%M")
            print(f"  Mới nhất  : {newest}")
        except (ValueError, OSError, TypeError):
            pass

    if data.get("top_engines"):
        engines = ", ".join(
            f"{_engine_label(item['engine'])}={item['count']}"
            for item in data["top_engines"]
        )
        print(f"  Engine    : {engines}")

    print(f"  Cache     : {'bật' if config.get('cache_enabled', True) else 'tắt'}")
    print(f"  Giới hạn  : {config.get('history_limit', 500)} mục")
    rust = native.status()
    print(
        "  Rust      : "
        + (f"có ({rust['version'] or rust['path']})" if rust["available"] else "chưa build (dùng Python)")
    )
    return 0


def _cmd_clear_history(args) -> int:
    if not args.yes:
        if not sys.stdin.isatty():
            print("⚠ Cần --yes khi chạy không tương tác để xóa lịch sử.", file=sys.stderr)
            return 2
        try:
            answer = input("Xóa toàn bộ lịch sử và cache SuperTrans? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if answer.strip().lower() not in ("y", "yes"):
            print("Đã hủy.")
            return 0

    deleted = store.clear_all()
    print(
        f"🗑 Đã xóa {deleted['translations']} bản dịch và "
        f"{deleted['replacements']} lần thay thế."
    )
    return 0


def _cmd_undo(args) -> int:
    ok, message = undo_last_replacement(force=args.force)
    print(("✅ " if ok else "⚠ ") + message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def _check(label: str, ok: bool, detail: str = "") -> None:
    symbol = "✅" if ok else "❌"
    suffix = f" — {detail}" if detail else ""
    print(f"  {symbol} {label}{suffix}")


def _cmd_doctor(config) -> int:
    print("🩺 SuperTrans Doctor")
    print(f"  Python   : {sys.version.split()[0]}")
    print(f"  Version  : {__version__}")
    print(f"  Config   : {CONFIG_FILE} ({'có' if os.path.exists(CONFIG_FILE) else 'chưa tạo'})")
    print(f"  Engine   : {config.get('default_engine', 'fast')} · {config.get('ai_model', '')}")

    print("\n📦 Phụ thuộc hệ thống")
    tools = {
        "dms": "DMS Launcher/Clipboard/Notepad",
        "fuzzel": "fallback Launcher",
        "wl-paste": "đọc clipboard/selection",
        "wl-copy": "ghi clipboard",
        "wtype": "dán tại chỗ + undo Ctrl+Z",
        "notify-send": "notification fallback",
        "niri": "phím tắt / nhận diện cửa sổ",
        "opencode": "engine AI",
    }
    for tool, purpose in tools.items():
        path = shutil.which(tool)
        _check(f"{tool:<12} ({purpose})", bool(path), path or "không tìm thấy")

    print("\n💾 Cache & lịch sử")
    data = store.stats()
    _check("SQLite khả dụng", not data.get("error"), data.get("path", ""))
    print(f"     {data.get('translations', 0)} bản dịch · {data.get('replacements', 0)} lần thay thế")
    _check("Cache đang bật", bool(config.get("cache_enabled", True)),
           f"giới hạn {config.get('history_limit', 500)} mục")
    _check("Đọc PRIMARY/CLIPBOARD", bool(shutil.which("wl-paste") or shutil.which("xclip")))
    _check("Undo bằng Ctrl+Z", bool(shutil.which("wtype")), "cần wtype")

    print("\n🖼 OCR")
    missing = missing_ocr_dependencies()
    _check("Công cụ chụp/OCR", not missing, ", ".join(missing) if missing else "slurp + grim + tesseract")
    langs, tess_dir = get_available_ocr_langs()
    _check("Ngôn ngữ tessdata", bool(langs), f"{', '.join(langs)} @ {tess_dir or 'mặc định'}")
    from super_trans.core import image_prep
    prep = image_prep.status()
    _check("Tăng cường ảnh", bool(prep["available"]),
           str(prep["backend"] or "không có Pillow/ImageMagick"))
    print(f"     PSM mặc định: {config.get('ocr_psm', 3)} · "
          f"preprocess: {'bật' if config.get('ocr_preprocess', True) else 'tắt'}")

    print("\n🦀 Helper Rust")
    rust = native.status()
    _check("super-trans-native", bool(rust["available"]),
           str(rust["version"] or rust["path"] or "chưa build (fallback Python)"))
    print(f"     Dùng cho văn bản >= {rust['threshold']} ký tự")

    print("\n🪟 Giao diện")
    _check("DMS shell", dms.available(), "dmenu/clipboard/notepad/notify")
    _check("Dynamic Island", dms.island_available(), "islandActivity")
    print(f"     Output mặc định: {config.get('output_mode', 'island')}")
    try:
        from super_trans.core.osd import osd_available
        _check("OSD GTK4", osd_available(), "Thẻ nổi Wayland")
    except Exception as exc:  # noqa: BLE001
        _check("OSD GTK4", False, str(exc))

    print("\n✅ Doctor hoàn tất. Các mục ❌ là tùy chọn trừ khi bạn dùng tính năng tương ứng.")
    return 0


def main() -> int:
    args = parse_args()
    config = load_config()

    # 1. Các lệnh quản trị (không cần văn bản đầu vào)
    if args.doctor:
        return _cmd_doctor(config)
    if args.stats:
        return _cmd_stats(config)
    if args.history is not None:
        return _cmd_history(args)
    if args.search is not None:
        return _cmd_search(args)
    if args.clear_history:
        return _cmd_clear_history(args)
    if args.undo:
        return _cmd_undo(args)

    # 2. Thu thập văn bản cần dịch
    collected = _collect_input(args, config)
    if collected is None:
        return 1
    input_text = collected.text
    if not input_text:
        return 0  # Người dùng hủy chọn/nhập

    if args.verbose and collected.source:
        print(f"ℹ Nguồn văn bản: {collected.source}", file=sys.stderr)

    # 3. Xác định ngôn ngữ nguồn & đích (ưu tiên dịch sang Tiếng Việt)
    src_lang, tgt_lang = resolve_languages(
        input_text,
        source_lang=args.from_lang,
        target_lang=args.to_lang,
        primary_target=config.get("primary_target_lang", "vi"),
        secondary_target=config.get("secondary_target_lang", "en"),
    )

    # 4. Xác định hình thức hiển thị trước khi dịch (để chọn chế độ AI phù hợp)
    out_mode = "replace" if args.replace else (
        args.output_mode or config.get("output_mode", "island")
    )
    engine_choice = args.engine or config.get("default_engine", "fast")

    wants_notepad = (
        engine_choice == "ai"
        and not args.no_popup
        and config.get("show_popup_on_ai", True)
        and args.output_mode is None
        and out_mode != "replace"
    )
    # Island/Launcher cần ngữ cảnh AI để hiển thị dòng phụ; vẫn không mở Notepad.
    want_analysis = (
        engine_choice == "ai"
        and out_mode in ("island", "launcher")
    )

    cache_enabled = bool(config.get("cache_enabled", True)) and not args.no_cache
    history_limit = int(config.get("history_limit", store.DEFAULT_HISTORY_LIMIT))
    engine_key = (
        f"ai:{config.get('ai_model', 'opencode/deepseek-v4.1-flash-free')}"
        if engine_choice == "ai"
        else "fast"
    )
    cache_allowed = cache_enabled and not args.refresh and not wants_notepad

    # 5. Dịch (cache -> engine, hoặc engine -> cache)
    translated = ""
    analysis = ""
    detected_src = src_lang
    active_engine_name = "Fast"
    cache_hit = False

    if cache_allowed:
        cached = store.lookup(input_text, src_lang, tgt_lang, engine_key)
        if cached:
            translated = cached.get("translated_text", "")
            detected_src = (
                cached.get("detected_lang")
                or cached.get("source_lang")
                or src_lang
            )
            base_name = "OpenCode AI" if engine_choice == "ai" else "Fast"
            active_engine_name = f"{base_name} (cache)"
            cache_hit = True
            if args.verbose:
                print("⚡ Cache hit — không gọi mạng.", file=sys.stderr)

    save_engine = engine_key
    if not cache_hit:
        if engine_choice == "ai":
            try:
                translated, analysis, detected_src, active_engine_name = _translate_with_ai(
                    input_text, src_lang, tgt_lang, config, wants_notepad,
                    want_analysis,
                )
            except Exception as exc:  # FastEngine fallback cũng thất bại
                print(f"❌ Lỗi dịch: {exc}", file=sys.stderr)
                return 1
            if active_engine_name.startswith("Fast"):
                save_engine = "fast"
        else:
            try:
                translated, detected_src = FastEngine().translate(
                    input_text, src_lang=src_lang, tgt_lang=tgt_lang
                )
                active_engine_name = "Fast"
            except Exception as exc:
                print(f"❌ Lỗi dịch: {exc}", file=sys.stderr)
                return 1

        if not translated:
            print("❌ Bộ máy dịch không trả về nội dung.", file=sys.stderr)
            return 1

        if cache_enabled:
            store.save_translation(
                input_text,
                translated,
                src_lang,
                tgt_lang,
                save_engine,
                detected_lang=detected_src,
                history_limit=history_limit,
            )

    # 6. AI Notepad (chỉ khi engine AI vừa phân tích xong)
    if wants_notepad and analysis:
        notepad_opened = open_in_dms_notepad(
            input_text, analysis, detected_src, tgt_lang
        )
        # Không mở thêm island/launcher khi DMS Notepad đã hiển thị đầy đủ.
        if notepad_opened and args.output_mode is None:
            out_mode = "none"

    # 7. Sao chép kết quả vào clipboard nếu được bật
    if not args.no_copy and config.get("auto_copy_to_clipboard", True):
        set_clipboard_text(translated)

    # 8. Hiển thị kết quả bằng các tiện ích sẵn có của hệ thống
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
            analysis=analysis,
            island_timeout_ms=config.get("island_timeout_ms", 10000),
        )

    # 9. In ra stdout cho terminal / script
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
