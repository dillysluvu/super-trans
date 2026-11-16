"""
Bộ kiểm thử tự động cho SuperTrans.

Các kiểm thử mặc định chạy hoàn toàn offline (mock network).
Đặt SUPERTRANS_LIVE_TESTS=1 để chạy thêm kiểm thử tích hợp với Google Translate.
"""

import argparse
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
from super_trans.core import (
    clipboard, dms, image_prep, island, island_watch, launcher, native,
    notifier, presentation, store,
)
from super_trans.core.clipboard import (
    SOURCE_CLIPBOARD,
    SOURCE_NONE,
    SOURCE_PRIMARY,
    Selection,
)
from super_trans.core.detector import is_vietnamese, resolve_languages
from super_trans.core.ocr import (
    TARGET_LANGS,
    get_available_ocr_langs,
    missing_ocr_dependencies,
    select_ocr_languages,
)
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine

# Toàn bộ test dùng DB tạm, không đụng lịch sử thật của người dùng.
_TEST_ROOT = tempfile.mkdtemp(prefix="super-trans-tests-")
os.environ["SUPERTRANS_DB"] = os.path.join(_TEST_ROOT, "history.db")


def tearDownModule():
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


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
    @mock.patch("super_trans.core.launcher.set_primary_text", return_value=True)
    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher.dms.send_paste", return_value=True)
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="foot")
    def test_replace_uses_shift_in_terminal(
        self, _focused, send_paste, _clipboard, _primary, _sleep, _which
    ):
        self.assertTrue(launcher.replace_selection_in_place("Xin chào"))
        send_paste.assert_called_once_with(shift=True)

    @mock.patch("super_trans.core.launcher._pick_item", return_value="")
    def test_launcher_items_are_minimal(self, pick):
        self.assertEqual(
            launcher.show_in_launcher("Hello", "Xin chào", "en", "vi"),
            "",
        )
        items = pick.call_args.args[0]
        self.assertEqual(items, [
            "📋 Hello : Xin chào",
            "✍️ Thay thế",
            "🧠 Phân tích",
        ])

    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="📋 Hello : Xin chào")
    def test_copy_action(self, _pick, clipboard):
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "copied")
        clipboard.assert_called_once_with("Xin chào")

    @mock.patch("super_trans.core.launcher.replace_selection_in_place",
                return_value=True)
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="✍️ Thay thế")
    def test_replace_action(self, _pick, replace):
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "replaced")
        replace.assert_called_once()

    @mock.patch("super_trans.core.launcher.open_in_dms_notepad", return_value=True)
    @mock.patch("super_trans.core.launcher.dms.toast", return_value=True)
    @mock.patch("super_trans.core.launcher.OpenCodeEngine")
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="🧠 Phân tích")
    def test_ai_action(self, _pick, engine_cls, _toast, notepad):
        engine_cls.return_value.analyze.return_value = (
            "Xin chào", "## 🔍 Phân tích", "en"
        )
        action = launcher.show_in_launcher("Hello", "Xin chào", "en", "vi")
        self.assertEqual(action, "opened_notepad")
        notepad.assert_called_once()

    @mock.patch("super_trans.core.launcher.open_in_dms_notepad", return_value=True)
    @mock.patch("super_trans.core.launcher.OpenCodeEngine")
    @mock.patch("super_trans.core.launcher._pick_item",
                return_value="🧠 Phân tích")
    def test_ai_action_reuses_existing_analysis(
        self, _pick, engine_cls, notepad
    ):
        action = launcher.show_in_launcher(
            "Hello", "Xin chào", "en", "vi",
            analysis="## 🔍 Phân tích\n\nNgữ cảnh có sẵn.",
        )
        self.assertEqual(action, "opened_notepad")
        engine_cls.assert_not_called()
        notepad.assert_called_once()
        self.assertIn("Ngữ cảnh có sẵn.", notepad.call_args.args[1])


class TestPresentation(unittest.TestCase):

    def test_compact_pair(self):
        self.assertEqual(
            presentation.compact_pair("Hello", "Xin chào"),
            "Hello : Xin chào",
        )
        pair = presentation.compact_pair("a" * 500, "b" * 500, 80)
        self.assertLessEqual(len(pair), 80)
        self.assertIn(" : ", pair)

    def test_short_context_skips_translation_and_markdown(self):
        analysis = (
            "## 🌐 Bản dịch\n\nXin chào\n\n"
            "## 🔍 Phân tích\n\n"
            "### Thành ngữ\n\n"
            "**Thành ngữ:** Hello dùng để chào hỏi.\n"
            "- Giải thích thêm.\n"
        )
        self.assertEqual(
            presentation.short_context(analysis),
            "Thành ngữ: Hello dùng để chào hỏi.",
        )

    def test_context_line(self):
        self.assertEqual(
            presentation.context_line(
                "OpenCode AI", "Lời chào", "en", "vi",
            ),
            "OpenCode AI · Lời chào",
        )
        self.assertEqual(
            presentation.context_line("Fast", "", "en", "vi"),
            "Fast · EN→VI",
        )


class TestIsland(unittest.TestCase):

    def test_build_payload_is_minimal(self):
        payload = island.build_payload(
            "Hello", "Xin chào", "en", "vi", "OpenCode AI",
            context="Lời chào", timeout_ms=1, screen="eDP-1",
        )
        self.assertEqual(payload["title"], "Hello : Xin chào")
        self.assertEqual(payload["subtitle"], "OpenCode AI · Lời chào")
        self.assertEqual(payload["body"], "Xin chào")
        self.assertEqual(payload["duration"], 2000)
        self.assertEqual(payload["screen"], "eDP-1")
        self.assertEqual(
            [action["id"] for action in payload["actions"]],
            ["copy", "analyze"],
        )

    def test_show_in_island_publishes_and_starts_watcher(self):
        with mock.patch.object(island.dms, "available", return_value=True), \
                mock.patch.object(island.dms, "island_available", return_value=True), \
                mock.patch.object(island.dms, "island_publish", return_value=True) as publish, \
                mock.patch.object(island, "_focused_output", return_value="eDP-1"), \
                mock.patch.object(island, "_spawn_watcher", return_value=True) as watcher:
            self.assertTrue(island.show_in_island(
                "Hello", "Xin chào", "en", "vi", "OpenCode AI",
                context="Lời chào", analysis="## 🔍 Phân tích\n\nLời chào.",
            ))
        source, activity_id, payload = publish.call_args.args
        self.assertTrue(source.startswith("supertrans-"))
        self.assertTrue(activity_id.startswith("result-"))
        self.assertEqual(payload["screen"], "eDP-1")
        watcher_payload = watcher.call_args.args[0]
        self.assertEqual(watcher_payload["source"], source)
        self.assertIn("Lời chào.", watcher_payload["analysis"])

    def test_show_in_island_derives_context_from_analysis(self):
        with mock.patch.object(island.dms, "available", return_value=True), \
                mock.patch.object(island.dms, "island_available", return_value=True), \
                mock.patch.object(island.dms, "island_publish", return_value=True) as publish, \
                mock.patch.object(island, "_focused_output", return_value="eDP-1"), \
                mock.patch.object(island, "_spawn_watcher", return_value=True):
            self.assertTrue(island.show_in_island(
                "Hello", "Xin chào", "en", "vi", "OpenCode AI",
                analysis="## 🔍 Phân tích\n\nLời chào thân mật.",
            ))
        self.assertEqual(
            publish.call_args.args[2]["subtitle"],
            "OpenCode AI · Lời chào thân mật.",
        )

    def test_show_in_island_unavailable(self):
        with mock.patch.object(island.dms, "available", return_value=False), \
                mock.patch.object(island.dms, "island_publish") as publish:
            self.assertFalse(island.show_in_island("Hello", "Xin chào"))
        publish.assert_not_called()

    def test_show_in_island_rolls_back_when_watcher_fails(self):
        with mock.patch.object(island.dms, "available", return_value=True), \
                mock.patch.object(island.dms, "island_available", return_value=True), \
                mock.patch.object(island.dms, "island_publish", return_value=True), \
                mock.patch.object(island.dms, "island_remove", return_value=True) as remove, \
                mock.patch.object(island, "_focused_output", return_value="eDP-1"), \
                mock.patch.object(island, "_spawn_watcher", return_value=False):
            self.assertFalse(island.show_in_island("Hello", "Xin chào"))
        remove.assert_called_once()

    @mock.patch("super_trans.core.island_watch.set_clipboard_text",
                return_value=True)
    @mock.patch("super_trans.core.island_watch.dms.toast", return_value=True)
    def test_copy_action(self, toast, clipboard):
        result = island_watch.handle_action("copy", {
            "original": "Hello",
            "translated": "Xin chào",
            "src_lang": "en",
            "tgt_lang": "vi",
        })
        self.assertEqual(result, "keep")
        clipboard.assert_called_once_with("Xin chào")
        toast.assert_called_once()

    @mock.patch("super_trans.core.island_watch.open_in_dms_notepad",
                return_value=True)
    @mock.patch("super_trans.core.island_watch.dms.toast", return_value=True)
    @mock.patch("super_trans.core.island_watch.OpenCodeEngine")
    def test_analyze_action_runs_engine_when_needed(
        self, engine_cls, _toast, notepad
    ):
        engine_cls.return_value.analyze.return_value = (
            "Xin chào", "## 🔍 Phân tích\n\nLời chào.", "en",
        )
        result = island_watch.handle_action("analyze", {
            "original": "Hello",
            "translated": "Xin chào",
            "src_lang": "en",
            "tgt_lang": "vi",
            "analysis": "",
            "ai_model": "opencode/test",
            "ai_timeout": 30,
        })
        self.assertEqual(result, "close")
        engine_cls.assert_called_once()
        notepad.assert_called_once()
        self.assertIn("Lời chào.", notepad.call_args.args[1])

    @mock.patch("super_trans.core.island_watch.open_in_dms_notepad",
                return_value=True)
    @mock.patch("super_trans.core.island_watch.OpenCodeEngine")
    def test_analyze_action_reuses_analysis(self, engine_cls, notepad):
        result = island_watch.handle_action("analyze", {
            "original": "Hello",
            "translated": "Xin chào",
            "src_lang": "en",
            "tgt_lang": "vi",
            "analysis": "## 🔍 Phân tích\n\nLời chào.",
        })
        self.assertEqual(result, "close")
        engine_cls.assert_not_called()
        notepad.assert_called_once()
        self.assertIn("Lời chào.", notepad.call_args.args[1])


class TestDMSIslandIPC(unittest.TestCase):

    @staticmethod
    def _completed(code=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(
            args=[], returncode=code, stdout=stdout, stderr=stderr,
        )

    @mock.patch("super_trans.core.dms._run")
    def test_availability(self, run):
        run.return_value = self._completed(
            stdout='{"islandPresent":true,"activitiesAvailable":true}',
        )
        self.assertTrue(dms.island_available())
        run.return_value = self._completed(
            stdout='{"islandPresent":true,"activitiesAvailable":false}',
        )
        self.assertFalse(dms.island_available())

    @mock.patch("super_trans.core.dms._run")
    def test_publish_uses_stdin(self, run):
        run.return_value = self._completed(stdout="ISLAND_ACTIVITY_PUBLISHED")
        self.assertTrue(dms.island_publish("src", "id", {"title": "Hello"}))
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            ["ipc", "call", "islandActivity", "publish", "src", "id", "-"],
        )
        self.assertIn('"title": "Hello"', kwargs["input_text"])

    @mock.patch("super_trans.core.dms._run")
    def test_list_and_actions(self, run):
        run.return_value = self._completed(
            stdout='[{"source":"src","id":"id"}]',
        )
        self.assertEqual(dms.island_list(), [{"source": "src", "id": "id"}])
        run.return_value = self._completed(
            stdout='[{"source":"src","id":"id","action":"copy"}]',
        )
        self.assertEqual(
            dms.island_poll_actions("src"),
            [{"source": "src", "id": "id", "action": "copy"}],
        )
        run.return_value = self._completed(stdout="ISLAND_ACTIVITY_REMOVED")
        self.assertTrue(dms.island_remove("src", "id"))


class TestNotifier(unittest.TestCase):

    @mock.patch("super_trans.core.notifier.dms.available", return_value=True)
    @mock.patch("super_trans.core.notifier.dms.toast", return_value=True)
    def test_dms_toast_is_minimal(self, toast, _available):
        self.assertTrue(notifier.send_dms_toast(
            "Hello", "Xin chào", "en", "vi", "OpenCode AI",
            context="Lời chào",
        ))
        title, details = toast.call_args.args[:2]
        self.assertEqual(title, "Hello : Xin chào")
        self.assertEqual(details, "OpenCode AI · Lời chào")

    @mock.patch("super_trans.core.notifier.show_in_island",
                return_value=True)
    @mock.patch("super_trans.core.notifier.show_in_launcher")
    def test_island_does_not_repeat_translation_as_context(
        self, launcher_mock, island_mock
    ):
        self.assertTrue(notifier.display_result(
            "Hello", "Xin chào", "en", "vi", "Fast",
            mode="island", analysis="Xin chào",
        ))
        launcher_mock.assert_not_called()
        self.assertEqual(island_mock.call_args.kwargs["context"], "")

    @mock.patch("super_trans.core.notifier.show_in_island",
                return_value=True)
    @mock.patch("super_trans.core.notifier.show_in_launcher")
    def test_island_success_skips_launcher(self, launcher_mock, island_mock):
        self.assertTrue(notifier.display_result(
            "Hello", "Xin chào", "en", "vi", "Fast",
            mode="island", analysis="## 🔍 Phân tích\n\nLời chào.",
        ))
        island_mock.assert_called_once()
        launcher_mock.assert_not_called()
        self.assertEqual(
            island_mock.call_args.kwargs["context"],
            "Lời chào.",
        )

    @mock.patch("super_trans.core.notifier.show_in_launcher",
                return_value="copied")
    @mock.patch("super_trans.core.notifier.show_in_island",
                return_value=False)
    def test_island_falls_back_to_launcher(self, _island, launcher_mock):
        self.assertTrue(notifier.display_result(
            "Hello", "Xin chào", "en", "vi", "Fast",
            mode="island", analysis="## 🔍 Phân tích\n\nLời chào.",
        ))
        launcher_mock.assert_called_once()
        self.assertEqual(
            launcher_mock.call_args.kwargs["analysis"],
            "## 🔍 Phân tích\n\nLời chào.",
        )


class TestCLI(unittest.TestCase):

    def setUp(self):
        store.clear_all()

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
        "ocr_preprocess": True,
        "ocr_psm": 3,
        "cache_enabled": False,
        "history_limit": 500,
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
        self.assertTrue(ai.call_args.args[5])  # want_analysis=True
        notepad.assert_called_once()
        display.assert_not_called()

    def test_explicit_output_overrides_notepad(self):
        code, output, ai, notepad, display = self._run_cli(
            ["--engine", "ai", "--output", "launcher", "xin chào"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Hello")
        self.assertFalse(ai.call_args.args[4])  # wants_notepad=False
        self.assertTrue(ai.call_args.args[5])   # want_analysis=True
        notepad.assert_not_called()
        display.assert_called_once()
        self.assertEqual(display.call_args.kwargs["mode"], "launcher")
        self.assertEqual(display.call_args.kwargs["analysis"], "## Analysis")

    def test_island_ai_requests_context_without_notepad(self):
        code, output, ai, notepad, display = self._run_cli(
            ["--engine", "ai", "--output", "island", "xin chào"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Hello")
        self.assertFalse(ai.call_args.args[4])  # wants_notepad=False
        self.assertTrue(ai.call_args.args[5])   # want_analysis=True
        notepad.assert_not_called()
        display.assert_called_once()
        self.assertEqual(display.call_args.kwargs["mode"], "island")


class TestConfig(unittest.TestCase):

    def test_sanitize_invalid_values(self):
        config = _sanitize({
            "default_engine": "unknown",
            "output_mode": "invalid",
            "ai_timeout_sec": "9999",
            "notification_timeout_ms": "10",
            "auto_copy_to_clipboard": "no",
            "ocr_psm": "99",
            "history_limit": "1",
            "island_timeout_ms": "1",
            "ocr_preprocess": "yes",
            "cache_enabled": "no",
        })
        self.assertEqual(config["default_engine"], "fast")
        self.assertEqual(config["output_mode"], "island")
        self.assertEqual(config["ai_timeout_sec"], 600)
        self.assertEqual(config["notification_timeout_ms"], 1000)
        self.assertEqual(config["island_timeout_ms"], 2000)
        self.assertTrue(config["auto_copy_to_clipboard"])
        self.assertEqual(config["ocr_psm"], 13)
        self.assertEqual(config["history_limit"], 10)
        self.assertTrue(config["ocr_preprocess"])
        self.assertTrue(config["cache_enabled"])


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


class TestStore(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(
            os.environ,
            {"SUPERTRANS_DB": os.path.join(self.temp.name, "history.db")},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def test_cache_roundtrip_and_scope(self):
        saved = store.save_translation(
            "Hello", "Xin chào", "auto", "vi", "fast",
            detected_lang="en", history_limit=50,
        )
        self.assertIsNotNone(saved)

        hit = store.lookup("Hello", "auto", "vi", "fast")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["translated_text"], "Xin chào")
        self.assertEqual(hit["detected_lang"], "en")
        self.assertEqual(hit["engine"], "fast")

        # Cùng văn bản nhưng khác đích/engine thì không được dùng chung cache.
        self.assertIsNone(store.lookup("Hello", "auto", "fr", "fast"))
        self.assertIsNone(store.lookup("Hello", "auto", "vi", "ai:model-x"))

    def test_empty_text_is_not_cached(self):
        self.assertIsNone(store.save_translation("", "x", "auto", "vi", "fast"))
        self.assertIsNone(store.lookup("", "auto", "vi", "fast"))

    def test_history_limit_prunes_old_entries(self):
        for index in range(6):
            store.save_translation(
                f"Text {index}", f"Bản dịch {index}",
                "auto", "vi", "fast", history_limit=3,
            )
        records = store.recent(20)
        self.assertEqual(len(records), 3)

    def test_search_matches_source_and_translation(self):
        store.save_translation("Thank you", "Cảm ơn bạn", "auto", "vi", "fast")
        store.save_translation("Good morning", "Chào buổi sáng", "auto", "vi", "fast")

        self.assertEqual(len(store.search("thank")), 1)
        self.assertEqual(len(store.search("CẢM ƠN")), 1)
        self.assertEqual(store.search("không có gì"), [])

    def test_replacement_and_undo(self):
        replacement_id = store.record_replacement(
            "Hello", "Xin chào", app_id="foot",
            source_lang="auto", target_lang="vi", engine="fast",
        )
        self.assertIsNotNone(replacement_id)

        latest = store.last_replacement()
        self.assertEqual(latest["original_text"], "Hello")
        self.assertEqual(latest["app_id"], "foot")

        self.assertTrue(store.mark_replacement_undone(replacement_id))
        self.assertFalse(store.mark_replacement_undone(replacement_id))
        self.assertIsNone(store.last_replacement())

    def test_clear_all(self):
        store.save_translation("Hello", "Xin chào", "auto", "vi", "fast")
        store.record_replacement("Hello", "Xin chào", app_id="foot")

        deleted = store.clear_all()
        self.assertEqual(deleted["translations"], 1)
        self.assertEqual(deleted["replacements"], 1)
        data = store.stats()
        self.assertEqual(data["translations"], 0)
        self.assertEqual(data["replacements"], 0)

    def test_stats(self):
        store.save_translation("Hello", "Xin chào", "auto", "vi", "fast")
        data = store.stats()
        self.assertTrue(data["exists"])
        self.assertEqual(data["translations"], 1)
        self.assertEqual(data["path"], os.environ["SUPERTRANS_DB"])


class TestSelection(unittest.TestCase):

    @mock.patch("super_trans.core.clipboard.get_clipboard_text", return_value="clip")
    @mock.patch("super_trans.core.clipboard.get_primary_selection", return_value="primary")
    def test_primary_is_preferred(self, _primary, _clip):
        selected = clipboard.get_selection(prefer_clipboard=True)
        self.assertEqual(selected, Selection("primary", SOURCE_PRIMARY))

    @mock.patch("super_trans.core.clipboard.get_clipboard_text", return_value="clip")
    @mock.patch("super_trans.core.clipboard.get_primary_selection", return_value="")
    def test_clipboard_fallback(self, _primary, _clip):
        selected = clipboard.get_selection(prefer_clipboard=True)
        self.assertEqual(selected, Selection("clip", SOURCE_CLIPBOARD))

    @mock.patch("super_trans.core.clipboard.get_clipboard_text", return_value="clip")
    @mock.patch("super_trans.core.clipboard.get_primary_selection", return_value="")
    def test_clipboard_fallback_can_be_disabled(self, _primary, _clip):
        selected = clipboard.get_selection(prefer_clipboard=False)
        self.assertEqual(selected, Selection("", SOURCE_NONE))

    @staticmethod
    def _args(**overrides):
        base = {
            "ocr": False, "ocr_file": None, "ocr_clipboard": False,
            "ocr_preprocess": None, "ocr_psm": None, "ocr_lang": None,
            "input": False, "clipboard": False, "selection": False,
            "replace": False, "text": [],
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_replace_accepts_primary(self):
        with mock.patch.object(
            cli, "get_selection", return_value=Selection("Hello", SOURCE_PRIMARY)
        ):
            collected = cli._collect_input(self._args(replace=True), {})
        self.assertIsNotNone(collected)
        self.assertEqual(collected.text, "Hello")
        self.assertEqual(collected.source, SOURCE_PRIMARY)

    def test_replace_refuses_clipboard_implicitly(self):
        # Mô phỏng hàm đọc trả về clipboard dù đã yêu cầu PRIMARY:
        # lớp bảo vệ thứ hai trong _collect_input phải từ chối.
        with mock.patch.object(
            cli, "get_selection", return_value=Selection("stale", SOURCE_CLIPBOARD)
        ):
            collected = cli._collect_input(self._args(replace=True), {})
        self.assertIsNone(collected)

    def test_replace_without_primary_returns_empty(self):
        with mock.patch.object(
            cli, "get_selection", return_value=Selection("", SOURCE_NONE)
        ):
            collected = cli._collect_input(self._args(replace=True), {})
        self.assertIsNotNone(collected)
        self.assertEqual(collected.text, "")

    def test_explicit_clipboard_source(self):
        with mock.patch.object(cli, "get_clipboard_text", return_value="clip"):
            collected = cli._collect_input(self._args(clipboard=True), {})
        self.assertEqual(collected.text, "clip")
        self.assertEqual(collected.source, SOURCE_CLIPBOARD)


class TestCLICache(unittest.TestCase):

    CONFIG = {
        "default_engine": "fast",
        "output_mode": "none",
        "ai_model": "opencode/test-model",
        "ai_timeout_sec": 120,
        "primary_target_lang": "vi",
        "secondary_target_lang": "en",
        "auto_copy_to_clipboard": False,
        "notification_timeout_ms": 6000,
        "show_popup_on_ai": True,
        "ocr_lang": "eng",
        "ocr_preprocess": True,
        "ocr_psm": 3,
        "cache_enabled": True,
        "history_limit": 50,
    }

    def setUp(self):
        store.clear_all()
        self.addCleanup(store.clear_all)

    def _run(self, argv, translate_result=("Xin chào", "en")):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["trans", *argv]), \
                mock.patch("super_trans.cli.load_config", return_value=self.CONFIG.copy()), \
                mock.patch("super_trans.cli.FastEngine") as engine_cls, \
                mock.patch("super_trans.cli.set_clipboard_text") as clipboard_mock, \
                contextlib.redirect_stdout(stdout):
            engine_cls.return_value.translate.return_value = translate_result
            code = cli.main()
        return code, stdout.getvalue(), engine_cls, clipboard_mock

    def test_cache_hit_skips_engine(self):
        store.save_translation(
            "Hello", "Xin chào", "auto", "vi", "fast",
            detected_lang="en", history_limit=50,
        )
        code, output, engine_cls, _clipboard = self._run(["Hello"])
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Xin chào")
        engine_cls.assert_not_called()

    def test_cache_miss_saves_translation(self):
        code, output, engine_cls, _clipboard = self._run(["Hello"])
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Xin chào")
        engine_cls.return_value.translate.assert_called_once()
        hit = store.lookup("Hello", "auto", "vi", "fast")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["translated_text"], "Xin chào")

    def test_no_cache_bypasses_read_and_write(self):
        store.save_translation(
            "Hello", "Bản cũ", "auto", "vi", "fast",
            detected_lang="en", history_limit=50,
        )
        code, output, engine_cls, _clipboard = self._run(
            ["--no-cache", "Hello"], translate_result=("Bản mới", "en")
        )
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Bản mới")
        engine_cls.return_value.translate.assert_called_once()
        hit = store.lookup("Hello", "auto", "vi", "fast")
        self.assertEqual(hit["translated_text"], "Bản cũ")

    def test_refresh_bypasses_read_but_updates_cache(self):
        store.save_translation(
            "Hello", "Bản cũ", "auto", "vi", "fast",
            detected_lang="en", history_limit=50,
        )
        code, output, engine_cls, _clipboard = self._run(
            ["--refresh", "Hello"], translate_result=("Bản mới", "en")
        )
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "Bản mới")
        engine_cls.return_value.translate.assert_called_once()
        hit = store.lookup("Hello", "auto", "vi", "fast")
        self.assertEqual(hit["translated_text"], "Bản mới")


class TestUndo(unittest.TestCase):

    @mock.patch("super_trans.core.launcher.store.mark_replacement_undone",
                return_value=True)
    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher._send_ctrl_z", return_value=True)
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="firefox")
    @mock.patch("super_trans.core.launcher.store.last_replacement")
    def test_undo_success(self, last, _focused, send, clipboard_mock, mark):
        last.return_value = {
            "id": 1, "original_text": "Hello", "translated_text": "Xin chào",
            "app_id": "firefox",
        }
        ok, message = launcher.undo_last_replacement()
        self.assertTrue(ok)
        self.assertIn("hoàn tác", message.lower())
        send.assert_called_once()
        mark.assert_called_once_with(1)
        clipboard_mock.assert_called_once_with("Hello")

    @mock.patch("super_trans.core.launcher.store.mark_replacement_undone")
    @mock.patch("super_trans.core.launcher._send_ctrl_z")
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="firefox")
    @mock.patch("super_trans.core.launcher.store.last_replacement")
    def test_undo_refuses_other_window(self, last, _focused, send, mark):
        last.return_value = {
            "id": 2, "original_text": "Hello", "translated_text": "Xin chào",
            "app_id": "foot",
        }
        ok, message = launcher.undo_last_replacement()
        self.assertFalse(ok)
        self.assertIn("khác", message)
        send.assert_not_called()
        mark.assert_not_called()

    @mock.patch("super_trans.core.launcher.store.mark_replacement_undone",
                return_value=True)
    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher._send_ctrl_z", return_value=True)
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="code")
    @mock.patch("super_trans.core.launcher.store.last_replacement")
    def test_undo_force_allows_other_window(self, last, _focused, send,
                                            _clipboard, mark):
        last.return_value = {
            "id": 3, "original_text": "Hello", "translated_text": "Xin chào",
            "app_id": "firefox",
        }
        ok, _message = launcher.undo_last_replacement(force=True)
        self.assertTrue(ok)
        send.assert_called_once()
        mark.assert_called_once_with(3)

    @mock.patch("super_trans.core.launcher.set_clipboard_text", return_value=True)
    @mock.patch("super_trans.core.launcher._send_ctrl_z")
    @mock.patch("super_trans.core.launcher._focused_app_id", return_value="foot")
    @mock.patch("super_trans.core.launcher.store.last_replacement")
    def test_undo_never_sends_ctrl_z_to_terminal(self, last, _focused, send,
                                                 clipboard_mock):
        last.return_value = {
            "id": 4, "original_text": "Hello", "translated_text": "Xin chào",
            "app_id": "foot",
        }
        ok, message = launcher.undo_last_replacement()
        self.assertFalse(ok)
        self.assertIn("terminal", message)
        send.assert_not_called()
        clipboard_mock.assert_called_once_with("Hello")

    @mock.patch("super_trans.core.launcher.store.last_replacement",
                return_value=None)
    def test_undo_without_history(self, _last):
        ok, message = launcher.undo_last_replacement()
        self.assertFalse(ok)
        self.assertIn("Không có", message)


class TestImagePreprocess(unittest.TestCase):

    def test_backend_status(self):
        status = image_prep.status()
        self.assertIn("backend", status)
        self.assertIn("available", status)

    @unittest.skipUnless(image_prep.PILLOW_AVAILABLE, "Pillow chưa cài")
    def test_dark_image_is_inverted_and_upscaled(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "dark.png")
            target = os.path.join(directory, "prepared.png")
            image = Image.new("L", (200, 60), 0)
            for x in range(20, 180):
                for y in range(24, 36):
                    image.putpixel((x, y), 255)
            image.save(source)

            path, backend = image_prep.preprocess_image(source, target)
            self.assertEqual(path, target)
            self.assertEqual(backend, "pillow")
            self.assertTrue(os.path.exists(target))

            with Image.open(target) as processed:
                self.assertGreater(processed.width, 200)
                histogram = processed.convert("L").histogram()
                total = max(1, sum(histogram))
                mean = sum(i * count for i, count in enumerate(histogram)) / total
                self.assertGreater(mean, 100)

    def test_fallback_returns_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "input.png")
            with open(source, "wb") as handle:
                handle.write(b"not-an-image")
            with mock.patch.object(image_prep, "PILLOW_AVAILABLE", False), \
                    mock.patch.object(image_prep, "_imagemagick_binary",
                                      return_value=None):
                path, backend = image_prep.preprocess_image(source)
        self.assertEqual(path, source)
        self.assertEqual(backend, "")


class TestOCRFile(unittest.TestCase):

    @mock.patch("super_trans.core.ocr.subprocess.run")
    @mock.patch("super_trans.core.ocr.get_available_ocr_langs",
                return_value=(["eng"], None))
    @mock.patch("super_trans.core.ocr.shutil.which", return_value="/usr/bin/tool")
    def test_ocr_from_file_skips_capture(self, _which, _langs, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Hello\n", stderr=""
        )
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            result = cli.capture_and_ocr(
                lang="eng", preprocess=False,
                image_path=handle.name, psm=6,
            )

        self.assertEqual(result, "Hello")
        command = run.call_args.args[0]
        self.assertEqual(command[0], "tesseract")
        self.assertIn(handle.name, command)
        self.assertIn("--psm", command)
        self.assertIn("6", command)
        self.assertNotIn("slurp", command)


class TestNativeHelper(unittest.TestCase):

    def test_short_text_does_not_spawn_helper(self):
        self.assertIsNone(native.split_text("Hello", 100))

    @unittest.skipUnless(native.available(), "Helper Rust chưa build")
    def test_native_split_preserves_content(self):
        text = "Câu tiếng Việt dài. " * 1000
        chunks = native.split_text(text, 500)
        self.assertIsNotNone(chunks)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
        self.assertEqual(
            "".join(text.split()),
            "".join("".join(chunks).split()),
        )

    def test_fast_engine_uses_native_result(self):
        with mock.patch(
            "super_trans.engines.fast_engine.native.split_text",
            return_value=["Đoạn A", "Đoạn B"],
        ) as native_split:
            chunks = FastEngine.split_text("x" * 5000, limit=1000)
        self.assertEqual(chunks, ["Đoạn A", "Đoạn B"])
        native_split.assert_called_once()

    def test_fast_engine_falls_back_when_native_returns_none(self):
        with mock.patch(
            "super_trans.engines.fast_engine.native.split_text",
            return_value=None,
        ):
            chunks = FastEngine.split_text("x" * 5000, limit=1000)
        self.assertEqual(len(chunks), 5)


class TestCLICommands(unittest.TestCase):

    @mock.patch("super_trans.cli.store.recent")
    def test_history_lists_records(self, recent):
        recent.return_value = [{
            "id": 1, "last_used_at": 1700000000, "source_lang": "auto",
            "detected_lang": "en", "target_lang": "vi", "engine": "fast",
            "use_count": 2, "source_text": "Hello", "translated_text": "Xin chào",
        }]
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["trans", "--history"]), \
                mock.patch("super_trans.cli.load_config", return_value={}), \
                contextlib.redirect_stdout(stdout):
            code = cli.main()
        self.assertEqual(code, 0)
        self.assertIn("Hello", stdout.getvalue())
        self.assertIn("Xin chào", stdout.getvalue())

    @mock.patch("super_trans.cli.store.clear_all")
    def test_clear_history_requires_yes_when_not_tty(self, clear):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["trans", "--clear-history"]), \
                mock.patch("super_trans.cli.load_config", return_value={}), \
                mock.patch.object(sys.stdin, "isatty", return_value=False), \
                contextlib.redirect_stdout(stdout):
            code = cli.main()
        self.assertEqual(code, 2)
        clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
