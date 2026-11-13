"""
Giao diện nhập liệu nhanh và hiển thị chi tiết tích hợp công cụ sẵn có
"""

from super_trans.core.launcher import prompt_input_via_launcher, open_in_dms_notepad

def prompt_input() -> str:
    """Mở ô nhập liệu nhanh từ bàn phím qua DMS Launcher."""
    return prompt_input_via_launcher()

def show_detail_dialog(title: str, text: str):
    """Mở bài phân tích chi tiết trong tiện ích DMS Notepad có sẵn."""
    open_in_dms_notepad(orig="", analysis=text, src_lang="auto", tgt_lang="vi")
