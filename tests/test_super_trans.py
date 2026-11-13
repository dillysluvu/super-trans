"""
Bộ kiểm thử tự động cho SuperTrans
Tối ưu hóa phát hiện ngôn ngữ Anh, Pháp, Trung -> Tiếng Việt
"""

import unittest
import sys
import os
import unicodedata

# Thêm đường dẫn project
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from super_trans.core.detector import is_vietnamese, resolve_languages
from super_trans.engines.fast_engine import FastEngine
from super_trans.engines.opencode_engine import OpenCodeEngine
from super_trans.core.clipboard import set_clipboard_text, get_selection_text
from super_trans.core.ocr import get_available_ocr_langs

class TestSuperTrans(unittest.TestCase):

    def test_language_detection(self):
        # Tiếng Việt có dấu chuẩn
        self.assertTrue(is_vietnamese("Xin chào thế giới! Hôm nay bạn khỏe không?"))
        self.assertTrue(is_vietnamese("Tôi muốn dịch đoạn này"))
        self.assertTrue(is_vietnamese("Đời là thế đấy"))

        # Tiếng Anh
        self.assertFalse(is_vietnamese("Hello world, this is a test."))
        self.assertFalse(is_vietnamese("Artificial intelligence and machine learning."))

        # Tiếng Pháp (chú ý: có chứa các dấu à, è, é, ê, ù, nhưng KHÔNG được nhận nhầm là tiếng Việt)
        self.assertFalse(is_vietnamese("Bonjour, comment ça va?"))
        self.assertFalse(is_vietnamese("À bientôt mon ami"))
        self.assertFalse(is_vietnamese("Merci beaucoup pour votre aide"))
        self.assertFalse(is_vietnamese("C'est la vie, mon cher"))
        self.assertFalse(is_vietnamese("Déjà vu"))

        # Tiếng Trung
        self.assertFalse(is_vietnamese("你好，很高兴见到你"))
        self.assertFalse(is_vietnamese("塞翁失马"))
        self.assertFalse(is_vietnamese("人工智能正在改变世界"))

    def test_resolve_languages_target_is_vietnamese(self):
        # Tiếng Anh -> Tiếng Việt
        src, tgt = resolve_languages("Good morning")
        self.assertEqual(tgt, "vi")

        # Tiếng Pháp -> Tiếng Việt
        src, tgt = resolve_languages("Bonjour mon ami")
        self.assertEqual(tgt, "vi")
        src, tgt = resolve_languages("C'est magnifique!")
        self.assertEqual(tgt, "vi")

        # Tiếng Trung -> Tiếng Việt
        src, tgt = resolve_languages("你好，明天见")
        self.assertEqual(tgt, "vi")

        # Tiếng Việt -> Tiếng Anh
        src, tgt = resolve_languages("Chào buổi sáng")
        self.assertEqual(src, "vi")
        self.assertEqual(tgt, "en")

    def test_fast_engine_multilang(self):
        engine = FastEngine()

        # Dịch Anh -> Việt
        trans_en, _ = engine.translate("Thank you very much", src_lang="auto", tgt_lang="vi")
        self.assertIn("cảm ơn", trans_en.lower())

        # Dịch Pháp -> Việt
        trans_fr, _ = engine.translate("Merci beaucoup", src_lang="auto", tgt_lang="vi")
        self.assertIn("cảm ơn", trans_fr.lower())

        # Dịch Trung -> Việt
        trans_zh, _ = engine.translate("谢谢你", src_lang="auto", tgt_lang="vi")
        self.assertIn("cảm ơn", trans_zh.lower())

    def test_ocr_languages_available(self):
        langs, tess_dir = get_available_ocr_langs()
        self.assertIn("eng", langs)
        self.assertIn("fra", langs)
        self.assertIn("chi_sim", langs)
        self.assertIn("vie", langs)

    def test_opencode_engine_discovery(self):
        engine = OpenCodeEngine()
        self.assertTrue(os.path.exists(engine.bin_path))

if __name__ == "__main__":
    unittest.main()
