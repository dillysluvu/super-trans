# 🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống
> **Được thiết kế và phối hợp xây dựng bởi Antigravity AI và OpenCode AI** dành riêng cho Fedora Linux & Niri Wayland Compositor.

---

## ✨ Điểm nổi bật ("Dùng ở mọi nơi, Cực kỳ dễ dùng")

1. **Dùng ở mọi nơi (System-wide Global Hotkeys)**:
   - **Bôi đen là dịch**: Đang đọc web (Brave/Chrome), tài liệu PDF, code (VS Code/Neovim), chat Slack/Discord... chỉ cần dùng chuột bôi đen đoạn văn bản và nhấn phím tắt, không cần copy.
   - **Chụp ảnh dịch màn hình (OCR)**: Xem video không có phụ đề rời, game, ảnh infographic, manga, hoặc giao diện app bị khóa copy? Chỉ cần nhấn phím tắt OCR để kéo chuột chụp vùng cần đọc và nhận diện dịch ngay.
   - **Hộp thoại gõ nhanh (Quick Prompt)**: Nhấn phím tắt để mở thanh gõ nhanh của Wayland (Fuzzel/Zenity), gõ hoặc dán câu cần dịch rồi nhấn Enter.
   - **Terminal CLI & Pipe**: Dễ dàng dùng trong terminal: `trans "hello"` hoặc `echo "..." | trans`.

2. **Hai động cơ dịch phối hợp (Dual Engine: Fast + OpenCode AI)**:
   - ⚡ **Fast Engine (Google)**: Tốc độ phản hồi cực nhanh (~100-200ms), 100% miễn phí, không cần token hay API key. Phù hợp đọc lướt nhanh.
   - 🧠 **Smart AI Engine (OpenCode)**: Kết nối trực tiếp với OpenCode CLI chạy DeepSeek/GLM/Nemotron. Dịch sâu theo ngữ cảnh thực tế, phân tích thành ngữ (idioms), tiếng lóng (slang), ngữ pháp và thuật ngữ kỹ thuật.

3. **Thông minh & Tiện lợi tối đa**:
   - **Tự động nhận diện ngôn ngữ 2 chiều**:
     - Phát hiện Tiếng Việt ➔ Tự động dịch sang Tiếng Anh.
     - Phát hiện Tiếng Anh / Ngoại ngữ khác ➔ Tự động dịch sang Tiếng Việt.
     - *Người dùng không bao giờ cần chỉnh ngôn ngữ thủ công.*
   - **Tự động lưu vào Clipboard**: Kết quả dịch luôn tự động được copy vào clipboard (`wl-copy`) để có thể `Ctrl+V` dán ngay lập tức vào văn bản của bạn.
   - **Thông báo máy tính (Desktop Notification)**: Hiển thị đẹp mắt trên hệ thống DMS / Notify-send.
   - **Popup chi tiết**: Tự động mở cửa sổ xem chi tiết khi dùng AI Engine hoặc khi dịch đoạn văn dài.

---

## ⌨️ Bảng phím tắt toàn hệ thống (Niri Wayland)

| Phím tắt | Chức năng | Mô tả chi tiết |
|---|---|---|
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> | **Dịch văn bản bôi đen** | Lấy text bạn đang bôi đen bằng chuột và dịch tức thì (~150ms). |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> | **Dịch chuyên sâu với OpenCode AI** | Phân tích nghĩa sâu, thành ngữ, sắc thái, ví dụ thực tế qua OpenCode. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>O</kbd> | **Chụp vùng màn hình (OCR)** | Kéo chuột khoanh vùng trên màn hình (ảnh, video) để đọc chữ và dịch. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>I</kbd> | **Hộp thoại nhập nhanh** | Mở thanh tìm kiếm/nhập liệu để gõ văn bản bất kỳ. |

*(Phím `Mod` thường là phím `Super` / `Windows` trên bàn phím)*

---

## 💻 Sử dụng qua dòng lệnh (CLI)

```bash
# Dịch nhanh thông thường (Tự động nhận diện Anh -> Việt hoặc Việt -> Anh)
trans "Good morning, how are you today?"
trans "Chào bạn, hôm nay trời rất đẹp!"

# Dịch chuyên sâu với OpenCode AI
trans -e ai "Under the weather"
trans -e ai "A blessing in disguise"

# Nhận text từ pipe
cat document.txt | trans
echo "Artificial Intelligence" | trans

# Chỉ định ngôn ngữ rõ ràng
trans --from en --to ja "Nice to meet you"

# Dịch nội dung đang bôi đen hoặc clipboard từ terminal
trans --selection
trans -s -e ai

# Kéo chuột chụp màn hình dịch OCR từ terminal
trans --ocr
```

---

## ⚙️ Cấu hình tùy chỉnh

File cấu hình nằm tại: `~/.config/super-trans/config.json`

```json
{
  "default_engine": "fast",
  "ai_model": "opencode/deepseek-v4.1-flash-free",
  "primary_target_lang": "vi",
  "secondary_target_lang": "en",
  "auto_copy_to_clipboard": true,
  "notification_timeout_ms": 6000,
  "show_popup_on_ai": true,
  "ocr_lang": "eng"
}
```

---

## 🛠️ Cài đặt & Gỡ bỏ

```bash
# Cài đặt hoặc nạp lại cấu hình:
./install.sh

# Gỡ bỏ:
./uninstall.sh
```
