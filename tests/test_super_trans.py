"""
Bộ kiểm thử tự động cho SuperTrans.

Các kiểm thử mặc định chạy hoàn toàn offline (mock network).
Đặt SUPERTRANS_LIVE_TESTS=1 để chạy thêm kiểm thử tích hợp với Google Translate.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import URLError

# Thêm đường dẫn project
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

import super_trans.cli as cli
from super_trans.config import _sanitize
from super_trans.core import dms
from super_trans.core import launcher
from super_trans.core.detector import is_vietnamese, resolve_languages
from super_trans.core.ocr import (
    TARGET_LANGS,
    get_available_ocr_langs,
    missing_ocr_dependencies,
    select_ocr_languages,
)
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestLanguageDetection(unittest.TestCase):

    def test_language_detection(self):
        # Tiếng Việt có dấu chuẩn
        self.assertTrue(is_vietnamese("Xin chào thế giới! Hôm nay bạn khỏe không?"))
        self.assertTrue(is_vietnamese("Tôi muốn dịch đoạn này"))
        self.assertTrue(is_vietnamese("Đời là thế đấy"))
        self.assertTrue(is_vietnamese("xin chào"))
        self.assertTrue(is_vietnamese("Đà Nẵng đẹp lắm"))
        # "la" là từ tiếng Pháp nhưng câu này vẫn phải là tiếng Việt
        self.assertTrue(is_vietnamese("Nó la mắng tôi"))

        # Tiếng Anh
        self.assertFalse(is_vietnamese("Hello world, this is a test."))
        self.assertFalse(is_vietnamese("Artificial intelligence and machine learning."))

        # Tiếng Pháp (có chung dấu à, è, é, ê, ô với tiếng Việt)
        self.assertFalse(is_vietnamese("Bonjour, comment ça va?"))
        self.assertFalse(is_vietnamese("À bientôt mon ami"))
        self.assertFalse(is_vietnamese("Merci beaucoup pour votre aide"))
        self.assertFalse(is_vietnamese("C'est la vie, mon cher"))
        self.assertFalse(is_vietnamese("Déjà vu"))
        self.assertFalse(is_vietnamese("La vie est belle"))
        self.assertFalse(is_vietnamese("Le chat est sur la table"))

        # Tiếng Trung
        self.assertFalse(is_vietnamese("你好，很高兴见到你"))
        self.assertFalse(is_vietnamese("塞翁失马"))
        self.assertFalse(is_vietnamese("人工智能正在改变世界"))

    def test_resolve_languages_target_is_vietnamese(self):
        # Tiếng Anh -> Tiếng Việt
        src, tgt = resolve_languages("Good morning")
        self.assertEqual((src, tgt), ("auto", "vi"))

        # Tiếng Pháp -> Tiếng Việt
        self.assertEqual(resolve_languages("Bonjour mon ami")[1], "vi")
        self.assertEqual(resolve_languages("C'est magnifique!")[1], "vi")

        # Tiếng Trung -> Tiếng Việt
        self.assertEqual(resolve_languages("你好，明天见")[1], "vi")

        # Tiếng Việt -> Tiếng Anh
        self.assertEqual(resolve_languages("Chào buổi sáng"), ("vi", "en"))

    def test_explicit_languages(self):
        # Chỉ định nguồn là tiếng Việt -> đích mặc định là tiếng Anh
        self.assertEqual(resolve_languages("Hello", source_lang="vi"), ("vi", "en"))
        # Chỉ định nguồn là ngoại ngữ -> đích mặc định là tiếng Việt
        self.assertEqual(resolve_languages("Xin chào", source_lang="en"), ("en", "vi"))
        # Chỉ định đầy đủ
        self.assertEqual(
            resolve_languages("Hello", source_lang="en", target_lang="fr"),
            ("en", "fr"),
        )
        # "auto" vẫn phải nhận diện tiếng Việt đúng
        self.assertEqual(resolve_languages("Chào bạn", source_lang="auto"), ("vi", "en"))


class TestFastEngine(unittest.TestCase):

    def test_parse_single_response(self):
        engine = FastEngine()
        payload = [[["Xin chào", "Hello", None, None]], None, "en"]
        with mock.patch(
            "super_trans.engines.fast_engine.urllib.request.urlopen",
            return_value=_FakeResponse(payload),
        ):
            translated, detected = engine.translate("Hello", src_lang="auto", tgt_lang="vi")
        self.assertEqual(translated, "Xin chào")
        self.assertEqual(detected, "en")

    def test_long_text_is_chunked(self):
        engine = FastEngine()
        text = "This is a sentence. " * 200
        payload = [[["Câu dịch.", "This is a sentence.", None, None]], None, "en"]
        chunks = engine.split_text(text.strip())

        with mock.patch(
            "super_trans.engines.fast_engine.urllib.request.urlopen",
            side_effect=lambda *args, **kwargs: _FakeResponse(payload),
        ) as urlopen:
            translated, _ = engine.translate(text, src_lang="auto", tgt_lang="vi")

        self.assertGreater(len(chunks), 1)
        self.assertEqual(urlopen.call_count, len(chunks))
        self.assertEqual(translated.count("Câu dịch."), len(chunks))

    def test_split_text_respects_limit(self):
        samples = [
            "Hello world. " * 300,
            "你好世界。" * 500,
            "Dòng một\nDòng hai\n" * 200,
            "x" * 5000,
        ]
        for sample in samples:
            chunks = FastEngine.split_text(sample, limit=500)
            self.assertTrue(chunks)
            self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
            # Không làm mất nội dung (bỏ qua khoảng trắng tại ranh giới)
            self.assertEqual(
                "".join(sample.split()),
                "".join("".join(chunks).split()),
            )

    def test_invalid_response(self):
        engine = FastEngine()
        with mock.patch(
            "super_trans.engines.fast_engine.urllib.request.urlopen",
            return_value=_FakeResponse([]),
        ):
            with self.assertRaises(RuntimeError):
                engine.translate("Hello")

    def test_network_error_is_retried(self):
        engine = FastEngine()
        with mock.patch(
            "super_trans.engines.fast_engine.urllib.request.urlopen",
            side_effect=URLError("offline"),
        ) as urlopen, mock.patch("super_trans.engines.fast_engine.time.sleep"):
            with self.assertRaises(RuntimeError):
                engine.translate("Hello")
        self.assertEqual(urlopen.call_count, 2)


@unittest.skipUnless(
    os.environ.get("SUPERTRANS_LIVE_TESTS") == "1",
    "Đặt SUPERTRANS_LIVE_TESTS=1 để chạy kiểm thử mạng",
)
class TestFastEngineLive(unittest.TestCase):

    def test_fast_engine_multilang(self):
        engine = FastEngine()
        for text in ("Thank you very much", "Merci beaucoup", "谢谢你"):
            translated, _ = engine.translate(text, src_lang="auto", tgt_lang="vi")
            self.assertIn("cảm ơn", translated.lower())


class TestOCR(unittest.TestCase):

    def test_ocr_languages_available(self):
        langs, _ = get_available_ocr_langs()
        self.assertIn("eng", langs)

    def test_select_ocr_languages_filters_missing(self):
        self.assertEqual(
            select_ocr_languages("eng+fra+chi_sim+vie", ["eng", "vie"]),
            "eng+vie",
        )
        self.assertEqual(select_ocr_languages("", ["eng", "fra"]), "eng")
        self.assertEqual(select_ocr_languages("deu", ["eng", "fra"]), "eng")
        self.assertEqual(
            select_ocr_languages("vie+eng+vie", ["eng", "vie"]),
            "vie+eng",
        )

    def test_prefers_directory_with_most_languages(self):
        with tempfile.TemporaryDirectory() as user_dir, \
                tempfile.TemporaryDirectory() as system_dir:
            open(os.path.join(user_dir, "eng.traineddata"), "w").close()
            for lang in ("eng", "vie"):
                open(os.path.join(system_dir, f"{lang}.traineddata"), "w").close()

            with mock.patch("super_trans.core.ocr.USER_TESSDATA_DIR", user_dir), \
                    mock.patch("super_trans.core.ocr.SYSTEM_TESSDATA_DIRS", (system_dir,)):
                langs, selected_dir = get_available_ocr_langs()

        self.assertEqual(langs, ["eng", "vie"])
        self.assertEqual(selected_dir, system_dir)

    def test_missing_dependencies(self):
        with mock.patch("super_trans.core.ocr.shutil.which", return_value=None):
            self.assertEqual(missing_ocr_dependencies(), ["slurp", "grim", "tesseract"])
        all_langs = list(TARGET_LANGS)
        self.assertIn("chi_sim", all_langs)


class TestDMS(unittest.TestCase):

    @staticmethod
    def _completed(returncode, stdout="", stderr=""):
        return subprocess.CompletedProcess(
            args=["dms"], returncode=returncode, stdout=stdout, stderr=stderr
        )

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_dmenu_ok(self, run, _which):
        run.return_value = self._completed(0, "🌟 Bản dịch\n")
        status, selected = dms.dmenu(["🌟 Bản dịch"], "Dịch")
        self.assertEqual(status, dms.DMENU_OK)
        self.assertEqual(selected, "🌟 Bản dịch")

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_dmenu_cancel_is_not_unavailable(self, run, _which):
        run.return_value = self._completed(1)
        self.assertEqual(dms.dmenu(["A"], "Dịch"), (dms.DMENU_CANCELLED, ""))

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_dmenu_usage_error_is_unavailable(self, run, _which):
        run.return_value = self._completed(1, stderr="Error: unknown flag: --icon")
        self.assertEqual(dms.dmenu(["A"], "Dịch"), (dms.DMENU_UNAVAILABLE, ""))

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_dmenu_shell_unreachable(self, run, _which):
        run.return_value = self._completed(2)
        self.assertEqual(dms.dmenu(["A"], "Dịch"), (dms.DMENU_UNAVAILABLE, ""))

    @mock.patch("super_trans.core.dms.shutil.which", return_value=None)
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_dms_missing(self, run, _which):
        self.assertEqual(dms.dmenu(["A"], "Dịch"), (dms.DMENU_UNAVAILABLE, ""))
        run.assert_not_called()

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_open_notepad(self, run, _which):
        run.return_value = self._completed(0, "NOTEPAD_OPEN_FILE_SUCCESS")
        self.assertTrue(dms.open_notepad("/tmp/a.md"))
        run.return_value = self._completed(0, "NOTEPAD_OPEN_FILE_FAILED")
        self.assertFalse(dms.open_notepad("/tmp/a.md"))

    @mock.patch("super_trans.core.dms.shutil.which", return_value="/usr/bin/dms")
    @mock.patch("super_trans.core.dms.subprocess.run")
    def test_send_paste_shift(self, run, _which):
        run.return_value = self._completed(0)
        self.assertTrue(dms.send_paste(shift=True))
        command = run.call_args.args[0]
        self.assertIn("--shift", command)


class TestLauncherActions(unittest.TestCase):

    def test_terminal_detection(self):
        self.assertTrue(launcher._is_terminal("foot"))
        self.assertTrue(launcher._is_terminal("org.gnome.console"))
        self.assertFalse(launcher._is_terminal("brave-browser"))
        self.assertFalse(launcher._is_terminal(""))

    @mock.patch("super_trans.core.launcher._fuzzel_pick")
    @mock.patch("super_trans.core.launcher.dms.dmenu",
                return_value=(dms.DMENU_CANCELLED, ""))
    def test_cancel_does_not_open_fuzzel(self, _dmenu, fuzzel):
        self.assertEqual(launcher._pick_item(["A"], "Dịch"), "")
        fuzzel.assert_not_called()

    @mock.patch("super_trans.core.launcher._fuzzel_pick",
                return_value=(dms.DMENU_OK, "B"))
    @mock.patch("super_trans.core.launcher.dms.dmenu",
                return_value=(dms.DMENU_UNAVAILABLE, ""))
    def test_unavailable_falls_back_to_fuzzel(self, _dmenu, _fuzzel):
        self.assertEqual(launcher._pick_item(["A"], "Dịch"), "B")

    @mock.patch("super_trans.core.launcher.shutil.which", return_value=None)
    @mock.patch("super_trans.core.launcher.time.sleep")
    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher.dms.send_paste", return_value=True)
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="foot")
    def test_replace_uses_shift_in_terminal(self, _focused, send_paste, _clipboard, _sleep, _which):
        self.assertTrue(launcher.replace_selection_in_place("Xin chào"))
        send_paste.assert_called_once_with(shift=True)

    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="🌟 [Bản dịch] Xin chào")
    def test_copy_action(self, _pick, clipboard):
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "copied")
        clipboard.assert_called_once_with("Xin chào")

    @mock.patch("super_trans.core.launcher.replace_selection_in_place",
                return_value=True)
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="✍️ [Thay thế tại chỗ] Dán đè")
    def test_replace_action(self, _pick, replace):
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "replaced")
        replace.assert_called_once()

    @mock.patch("super_trans.core.launcher.open_in_dms_notepad", return_value=True)
    @mock.patch("super_trans.core.launcher.dms.toast", return_value=True)
    @mock.patch("super_trans.core.launcher.OpenCodeEngine")
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="🧠 [Phân tích AI] Mở Notepad")
    def test_ai_action(self, _pick, engine_cls, _toast, notepad):
        engine_cls.return_value.analyze.return_value = (
            "Xin chào", "## 🔍 Phân tích", "en"
        )
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "opened_notepad")
        notepad.assert_called_once()


class TestCLI(unittest.TestCase):

    CONFIG = {
        "default_engine": "ai",
        "output_mode": "launcher",
        "ai_model": "opencode/deepseek-v4.1-flash-free",
        "ai_timeout_sec": 120,
        "primary_target_lang": "vi",
        "secondary_target_lang": "en",
        "auto_copy_to_clipboard": True,
        "notification_timeout_ms": 6000,
        "show_popup_on_ai": True,
        "ocr_lang": "eng",
    }

    def _run_cli(self, argv, ai_result=("Hello", "## Analysis", "vi", "OpenCode AI")):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["trans", *argv]), \
                mock.patch("super_trans.cli.load_config", return_value=self.CONFIG.copy()), \
                mock.patch("super_trans.cli._translate_with_ai", return_value=ai_result) as ai, \
                mock.patch("super_trans.cli.open_in_dms_notepad", return_value=True) as notepad, \
                mock.patch("super_trans.cli.display_result", return_value=True) as display, \
                mock.patch("super_trans.cli.set_clipboard_text", return_value=True), \
                contextlib.redirect_stdout(stdout):
            code = cli.main()
        return code, stdout.getvalue(), ai, notepad, display

    def test_ai_notepad_skips_duplicate_launcher(self):
        code, output, ai, notepad, display = self._run_cli(["xin chào"])
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Hello")
        self.assertTrue(ai.call_args.args[4])  # wants_notepad=True
        notepad.assert_called_once()
        display.assert_not_called()

    def test_explicit_output_overrides_notepad(self):
        code, output, ai, notepad, display = self._run_cli(
            ["--engine", "ai", "--output", "launcher", "xin chào"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Hello")
        self.assertFalse(ai.call_args.args[4])  # wants_notepad=False
        notepad.assert_not_called()
        display.assert_called_once()
        self.assertEqual(display.call_args.kwargs["mode"], "launcher")


class TestConfig(unittest.TestCase):

    def test_sanitize_invalid_values(self):
        config = _sanitize({
            "default_engine": "unknown",
            "output_mode": "invalid",
            "ai_timeout_sec": "9999",
            "notification_timeout_ms": "10",
            "auto_copy_to_clipboard": "no",
        })
        self.assertEqual(config["default_engine"], "fast")
        self.assertEqual(config["output_mode"], "launcher")
        self.assertEqual(config["ai_timeout_sec"], 600)
        self.assertEqual(config["notification_timeout_ms"], 1000)
        self.assertTrue(config["auto_copy_to_clipboard"])


class TestOpenCodeEngine(unittest.TestCase):

    def test_clean_output_removes_ansi_and_logs(self):
        raw = "\x1b[32m> build\x1b[0m\n```\nHello\n```\n"
        self.assertEqual(OpenCodeEngine._clean_output(raw), "Hello")

    def test_engine_discovery(self):
        engine = OpenCodeEngine()
        if not (os.path.exists(engine.bin_path) or shutil.which(engine.bin_path)):
            self.skipTest("OpenCode CLI chưa được cài đặt")
        self.assertTrue(os.path.exists(engine.bin_path))

    def test_analyze_parses_markers(self):
        engine = OpenCodeEngine()
        output = "<<<TRANSLATION>>>\nXin chào\n<<<ANALYSIS>>>\n- Thành ngữ: ..."
        with mock.patch.object(engine, "_run_prompt", return_value=output):
            translation, analysis, src = engine.analyze("Hello", src_lang="en", tgt_lang="vi")
        self.assertEqual(translation, "Xin chào")
        self.assertIn("## 🔍 Phân tích", analysis)
        self.assertIn("Thành ngữ", analysis)
        self.assertEqual(src, "en")


if __name__ == "__main__":
    unittest.main()
