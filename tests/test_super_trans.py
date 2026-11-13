"""
Bộ kiểm thử tự động cho SuperTrans
"""

import unittest
import sys
import os

# Thêm đường dẫn project
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from super_trans.core.detector import is_vietnamese, resolve_languages
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine
from super_trans.core.clipboard import set_clipboard_text, get_selection_text

class TestSuperTrans(unittest.TestCase):

    def test_language_detection(self):
        # Tiếng Việt có dấu
        self.assertTrue(is_vietnamese("Xin chào thế giới! Hôm nay bạn khỏe không?"))
        self.assertTrue(is_vietnamese("Tôi muốn dịch đoạn này"))

        # Tiếng Anh
        self.assertFalse(is_vietnamese("Hello world, this is a test."))
        self.assertFalse(is_vietnamese("Artificial intelligence and machine learning."))

    def test_resolve_languages(self):
        # Auto En -> Vi
        src, tgt = resolve_languages("Good morning")
        self.assertEqual(src, "auto")
        self.assertEqual(tgt, "vi")

        # Auto Vi -> En
        src, tgt = resolve_languages("Chào buổi sáng")
        self.assertEqual(src, "vi")
        self.assertEqual(tgt, "en")

    def test_fast_engine(self):
        engine = FastEngine()
        translated, src = engine.translate("Thank you very much", src_lang="auto", tgt_lang="vi")
        self.assertTrue(len(translated) > 0)
        self.assertIn("cảm ơn", translated.lower())

    def test_clipboard_roundtrip(self):
        test_str = "SuperTrans_Test_String_12345"
        success = set_clipboard_text(test_str)
        if success:
            got = get_selection_text()
            # Kiểm tra xem clipboard có nhận chuỗi không
            self.assertTrue(len(got) > 0)

    def test_opencode_engine_discovery(self):
        engine = OpenCodeEngine()
        self.assertTrue(os.path.exists(engine.bin_path))

if __name__ == "__main__":
    unittest.main()
