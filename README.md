# 🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống
> **Hợp tác phát triển giữa Antigravity AI và OpenCode AI**, tối ưu hóa riêng cho **Fedora Linux, Niri Wayland Compositor và DMS Shell**.

---

## ✨ Triết lý thiết kế ("Tối giản – Đồng nhất – Tận dụng tiện ích có sẵn")

Thay vì hiển thị dạng thông báo hay pop-up rời rạc gây rối mắt, **SuperTrans** kết hợp trực tiếp vào **các tiện ích sẵn có của hệ thống DMS**:

1. **Giao diện DMS Launcher / Spotlight (`dms dmenu`)**:
   - Khi dịch, kết quả hiển thị ngay trong cửa sổ **DMS Launcher** (chính là cửa sổ tìm kiếm người dùng hay dùng khi bấm `Mod+D`).
   - Sử dụng chung 100% font chữ, hiệu ứng mờ (*blur*), màu sắc theme và cách điều hướng phím mũi tên / Enter / Esc của hệ thống.
   - Các dòng tùy chọn trong Launcher:
     - 🌟 **Bản dịch**: `Xin chào, hôm nay bạn thế nào?` (Enter để sao chép).
     - ✍️ **Thay thế tại chỗ**: Dán đè kết quả trực tiếp vào vị trí con trỏ văn bản.
     - 🧠 **Phân tích OpenCode AI**: Mở phân tích chuyên sâu (thành ngữ, ngữ pháp) trong DMS Notepad.
     - 📋 **Bản gốc**: Xem lại văn bản nguồn.

2. **Thay thế tại chỗ vô hình (In-Place Replace qua `wtype`)**:
   - Khi đang gõ văn bản, email, chat Discord/Slack hoặc code: Bôi đen câu tiếng Anh/Pháp/Trung ➔ nhấn phím tắt **`Mod + Alt + R`** ➔ **Văn bản được dịch và thay thế trực tiếp ngay tại con trỏ**!
   - **0 thông báo, 0 cửa sổ phụ**, trải nghiệm liền mạch như một tính năng có sẵn của hệ điều hành.

3. **Tiện ích DMS Notepad (`Mod+Shift+N`)**:
   - Các bài phân tích chuyên sâu của OpenCode AI (thành ngữ tứ tự tiếng Trung, thành ngữ tiếng Pháp, cấu trúc câu) được hiển thị dạng Markdown trực tiếp trong tiện ích ghi chú **DMS Notepad**.

4. **Tiện ích DMS Clipboard Manager (`Mod+V`)**:
   - Mọi bản dịch đều tự động nằm ở đầu danh sách Clipboard để dán bất cứ lúc nào.

---

## ⌨️ Bảng phím tắt toàn hệ thống (Niri Wayland)

| Phím tắt | Chức năng | Cơ chế hoạt động với tiện ích hệ thống |
|---|---|---|
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> | **Xem bản dịch trong DMS Launcher** | Bôi đen text ➔ Mở menu kết quả trong Spotlight Launcher của DMS (chọn Copy, Dán đè, hoặc Phân tích AI). |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>R</kbd> | **Thay thế trực tiếp tại chỗ** | Bôi đen text ➔ Tự động dịch và gõ thay thế ngay tại chỗ con trỏ (`wtype`), không hiện thông báo. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> | **Phân tích chuyên sâu trong DMS Notepad** | Bôi đen text ➔ OpenCode AI phân tích thành ngữ, điển tích, ngữ pháp và mở trong DMS Notepad. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>O</kbd> | **Chụp vùng màn hình OCR** | Kéo chuột quét ảnh/video (Anh, Pháp, Trung) ➔ Mở kết quả trong DMS Launcher. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>I</kbd> | **Hộp thoại nhập liệu nhanh** | Mở thanh tìm kiếm DMS Launcher để gõ bất kỳ câu nào cần dịch. |

*(Phím `Mod` là phím `Super` / `Windows` trên bàn phím)*

---

## 💻 Sử dụng qua dòng lệnh (CLI)

```bash
# Dịch nhanh dòng lệnh (Anh/Pháp/Trung -> Tiếng Việt)
trans "Thank you very much"
trans "Merci beaucoup pour votre aide"
trans "非常感谢您的宝贵建议"

# Thay thế trực tiếp văn bản đang bôi đen từ terminal
trans --replace
trans -r

# Mở kết quả trong DMS Launcher
trans --selection --output launcher

# Phân tích chuyên sâu với OpenCode AI và mở trong DMS Notepad
trans -e ai "塞翁失马"

# Nhận dữ liệu từ pipe
echo "Artificial Intelligence" | trans
```

---

## ⚙️ Cấu hình tùy chỉnh

File cấu hình nằm tại: [`~/.config/super-trans/config.json`](file:///home/uyvu/.config/super-trans/config.json)

```json
{
  "default_engine": "fast",
  "output_mode": "launcher",
  "ai_model": "opencode/deepseek-v4.1-flash-free",
  "primary_target_lang": "vi",
  "secondary_target_lang": "en",
  "auto_copy_to_clipboard": true,
  "show_popup_on_ai": true,
  "ocr_lang": "eng+fra+chi_sim+vie"
}
```
Các giá trị của `output_mode`:
- `"launcher"`: Mở trong DMS Spotlight Launcher (Mặc định).
- `"replace"`: Thay thế tại chỗ bằng `wtype` (0 cửa sổ).
- `"osd"`: Thẻ Wayland OSD nổi.
- `"dms_toast"`: Đảo động Dynamic Island của DMS.
