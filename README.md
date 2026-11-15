# 🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống

> **Hợp tác phát triển giữa Antigravity AI và OpenCode AI**, tối ưu hóa riêng cho **Fedora Linux, Niri Wayland Compositor và DMS Shell**.

---

## ✨ Triết lý thiết kế ("Tối giản – Đồng nhất – Tận dụng tiện ích có sẵn")

Thay vì hiển thị thông báo hay pop-up rời rạc gây rối mắt, **SuperTrans** kết hợp trực tiếp vào **các tiện ích sẵn có của hệ thống DMS**:

1. **DMS Launcher / Spotlight (`dms dmenu`)**
   - Kết quả dịch hiện ngay trong cửa sổ tìm kiếm quen thuộc (`Mod+D`).
   - Dùng chung font chữ, hiệu ứng mờ, màu theme và điều hướng phím của DMS.
   - Các hành động: **Sao chép bản dịch**, **Thay thế tại chỗ**, **Phân tích AI**, **Xem bản gốc**.

2. **Thay thế tại chỗ vô hình (`dms clipboard send-paste` / `wtype`)**
   - Bôi đen câu tiếng Anh/Pháp/Trung ➔ nhấn `Mod+Alt+R` ➔ văn bản được dịch và thay thế ngay tại con trỏ.
   - Tự nhận biết terminal để dùng `Ctrl+Shift+V` thay vì `Ctrl+V`.
   - **0 thông báo, 0 cửa sổ phụ**, trải nghiệm liền mạch như tính năng hệ điều hành.

3. **DMS Notepad**
   - Bài phân tích chuyên sâu của OpenCode AI (thành ngữ, điển tích, ngữ pháp, sắc thái) được lưu thành Markdown và mở trong **DMS Notepad**.
   - Không mở thêm Launcher trùng lặp khi Notepad đã hiển thị kết quả.

4. **DMS Clipboard Manager**
   - Mọi bản dịch tự động nằm trong lịch sử clipboard của DMS, sẵn sàng dán bất cứ lúc nào.

5. **Cơ chế dự phòng thông minh**
   - `dms dmenu` ➔ `fuzzel`
   - `dms clipboard` ➔ `wl-copy` + `wtype`
   - `dms notify` ➔ `notify-send`
   - `DMS Notepad` ➔ `xdg-open` ➔ notification
   - FastEngine ➔ OpenCode AI lỗi thì tự quay về FastEngine, không làm gián đoạn công việc.

---

## 📋 Yêu cầu hệ thống

| Thành phần | Vai trò | Ghi chú |
|---|---|---|
| `python3` | Chạy SuperTrans | Bắt buộc |
| `wl-clipboard` | Đọc/ghi clipboard Wayland | Khuyến nghị |
| `wtype` | Dự phòng dán tại chỗ | Khuyến nghị |
| `slurp`, `grim`, `tesseract` | OCR vùng màn hình | Cần cho `--ocr` |
| `dms` | Launcher, Notepad, Clipboard, Toast | Tùy chọn, có fallback |
| `fuzzel` | Fallback Launcher | Tùy chọn |
| `opencode` | Engine AI | Cần cho `-e ai` |
| GTK4 + `gtk4-layer-shell` | Thẻ OSD nổi | Tùy chọn cho `--output osd` |

Cài đặt gói cơ bản trên Fedora:

```bash
sudo dnf install python3 wl-clipboard wtype slurp grim tesseract
```

---

## 🚀 Cài đặt

```bash
git clone <repository-url> ~/trans
cd ~/trans
./install.sh
```

Trình cài đặt sẽ:

- Liên kết lệnh `super-trans` và `trans` vào `~/.local/bin`.
- Tải các gói OCR `fra`, `chi_sim`, `vie` vào `~/.local/share/tessdata` (nếu thiếu).
- Tạo phím tắt Niri tại `~/.config/niri/dms/trans.kdl` và thêm include vào `config.kdl`.
- Nạp lại cấu hình Niri nếu `niri validate` thành công.

Chỉ cài CLI, không tạo phím tắt Niri:

```bash
./install.sh --no-niri
```

Cài đặt như một gói Python (tùy chọn, dùng pipx):

```bash
pipx install .
```

Gỡ cài đặt:

```bash
./uninstall.sh          # Giữ lại cấu hình
./uninstall.sh --purge  # Xóa cả cấu hình và cache phân tích
```

---

## ⌨️ Phím tắt toàn hệ thống (Niri Wayland)

| Phím tắt | Chức năng | Cơ chế hoạt động |
|---|---|---|
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> | **Xem bản dịch trong DMS Launcher** | Bôi đen text ➔ mở menu kết quả trong Spotlight (Copy, Dán đè, Phân tích AI). |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>R</kbd> | **Thay thế trực tiếp tại chỗ** | Bôi đen text ➔ dịch và dán đè ngay tại con trỏ, không hiện thông báo. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> | **Phân tích chuyên sâu** | OpenCode AI phân tích thành ngữ, điển tích, ngữ pháp và mở trong DMS Notepad. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>O</kbd> | **Chụp vùng màn hình OCR** | Kéo chuột quét ảnh/video (Anh, Pháp, Trung) ➔ mở kết quả trong DMS Launcher. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>I</kbd> | **Hộp thoại nhập liệu nhanh** | Mở thanh nhập liệu DMS Launcher để gõ câu cần dịch. |

*(Phím `Mod` là `Super` / `Windows` trên bàn phím.)*

---

## 💻 Sử dụng qua dòng lệnh (CLI)

```bash
# Dịch nhanh (Anh/Pháp/Trung -> Tiếng Việt)
trans "Thank you very much"
trans "Merci beaucoup pour votre aide"
trans "非常感谢您的宝贵建议"

# Nhận dữ liệu từ pipe
echo "Artificial Intelligence" | trans

# Thay thế trực tiếp văn bản đang bôi đen
trans --replace
trans -r

# Mở kết quả trong DMS Launcher
trans --selection --output launcher

# Phân tích chuyên sâu bằng OpenCode AI (mở DMS Notepad)
trans -e ai "塞翁失马"

# Chỉ lấy bản dịch sạch, không mở Notepad
trans -e ai --no-popup "塞翁失马"
trans -e ai --output none "塞翁失马"

# OCR vùng màn hình với ngôn ngữ tùy chọn
trans --ocr --ocr-lang "eng+vie"

# Hiển thị bằng thẻ OSD nổi thay vì Launcher
trans --output osd "Good morning"
```

### Các tùy chọn chính

| Tùy chọn | Mô tả |
|---|---|
| `-s`, `--selection` | Lấy văn bản đang bôi đen (PRIMARY) hoặc clipboard. |
| `-r`, `--replace` | Dịch và thay thế trực tiếp tại vị trí con trỏ. |
| `-o`, `--ocr` | Kéo chuột chụp vùng màn hình và OCR. |
| `--ocr-lang` | Ghi đè ngôn ngữ Tesseract, ví dụ `eng+fra+chi_sim+vie`. |
| `-i`, `--input` | Mở ô nhập liệu nhanh qua DMS Launcher. |
| `-e`, `--engine` | `fast` (Google GTX) hoặc `ai` (OpenCode). |
| `-m`, `--output` | `launcher`, `replace`, `osd`, `dms_toast`, `notification`, `none`. |
| `--from`, `--to` | Chỉ định ngôn ngữ nguồn/đích. |
| `--no-copy` | Không tự động sao chép kết quả vào clipboard. |
| `--no-popup` | Không mở DMS Notepad khi dùng engine AI. |

---

## ⚙️ Cấu hình

File cấu hình: `~/.config/super-trans/config.json`

```json
{
  "default_engine": "fast",
  "output_mode": "launcher",
  "ai_model": "opencode/deepseek-v4.1-flash-free",
  "ai_timeout_sec": 120,
  "primary_target_lang": "vi",
  "secondary_target_lang": "en",
  "auto_copy_to_clipboard": true,
  "notification_timeout_ms": 6000,
  "show_popup_on_ai": true,
  "ocr_lang": "eng+fra+chi_sim+vie"
}
```

| Khóa | Ý nghĩa |
|---|---|
| `default_engine` | `fast` hoặc `ai`. |
| `output_mode` | Chế độ hiển thị mặc định. |
| `ai_model` | Model OpenCode dùng cho engine AI. |
| `ai_timeout_sec` | Thời gian chờ tối đa cho OpenCode (10–600 giây). |
| `primary_target_lang` | Đích cho văn bản ngoại ngữ (mặc định `vi`). |
| `secondary_target_lang` | Đích cho văn bản tiếng Việt (mặc định `en`). |
| `auto_copy_to_clipboard` | Tự động đưa bản dịch vào clipboard/DMS Clipboard. |
| `show_popup_on_ai` | Mở DMS Notepad khi dùng engine AI. |
| `ocr_lang` | Danh sách ngôn ngữ Tesseract mặc định. |

Giá trị `output_mode`:

- `launcher`: DMS Spotlight Launcher (mặc định), fallback `fuzzel`.
- `replace`: Thay thế tại chỗ bằng DMS Clipboard/wtype.
- `osd`: Thẻ Wayland OSD nổi (GTK4 + Layer Shell).
- `dms_toast`: Toast trên Dynamic Island của DMS.
- `notification`: Notification desktop.
- `none`: Chỉ in ra stdout.

---

## 🧠 Cách hoạt động của engine AI

- `trans -e ai "..."` gọi OpenCode với prompt yêu cầu **bản dịch sạch** và **phân tích Markdown**.
- Bài phân tích được lưu tại `~/.cache/super-trans/super-trans-analysis-*.md` và mở trong DMS Notepad.
- Mặc định, khi Notepad đã mở, SuperTrans **không mở thêm Launcher** để tránh trùng lặp.
- Nếu chỉ định rõ `--output` (ví dụ `--output launcher`), SuperTrans dùng bản dịch sạch và bỏ qua Notepad.
- Nếu OpenCode lỗi hoặc quá thời gian, SuperTrans tự chuyển sang FastEngine và báo lỗi ra stderr.

---

## 🔍 OCR đa ngôn ngữ

- `install.sh` tự tải `fra`, `chi_sim`, `vie` (và `eng` nếu chưa có) vào `~/.local/share/tessdata`.
- SuperTrans tự chọn thư mục tessdata có nhiều ngôn ngữ nhất và **lọc bỏ ngôn ngữ chưa cài** thay vì để Tesseract báo lỗi.
- Vùng chọn được chụp bằng `slurp` + `grim`, sau đó nhận diện bằng `tesseract`.
- Nhấn `Esc` khi chọn vùng để hủy mà không báo lỗi.

---

## 🧪 Kiểm thử

```bash
# Toàn bộ kiểm thử offline (mock mạng)
python3 -m unittest discover -s tests -v

# Kiểm thử tích hợp thật với Google Translate
SUPERTRANS_LIVE_TESTS=1 python3 -m unittest discover -s tests -v
```

Bộ kiểm thử bao quát: nhận diện Việt/Pháp/Trung, chia nhỏ văn bản dài, parse phản hồi dịch, retry mạng, lọc ngôn ngữ OCR, trạng thái DMS dmenu (OK/cancel/không khả dụng), và logic tránh mở trùng Notepad + Launcher.

---

## 🛠️ Khắc phục sự cố

**Không thấy kết quả trong DMS Launcher**
- Kiểm tra `dms ipc call toast status` trả về trạng thái hợp lệ.
- SuperTrans sẽ tự fallback sang `fuzzel` nếu DMS shell không phản hồi.
- Nếu cả hai đều không có, dùng `trans --output notification "..."`.

**Phím tắt không hoạt động**
- Kiểm tra `~/.config/niri/config.kdl` có dòng `include optional=true "dms/trans.kdl"`.
- Chạy `niri validate` và `niri msg action load-config-file`.
- Đảm bảo `~/.local/bin` nằm trong `PATH` của phiên Niri.

**Không dán đè được trong terminal**
- SuperTrans tự phát hiện terminal và dùng `Ctrl+Shift+V`; nếu terminal có app_id lạ, thêm tên vào `TERMINAL_APP_IDS` trong `super_trans/core/launcher.py`.

**OCR báo thiếu ngôn ngữ**
- Kiểm tra `ls ~/.local/share/tessdata`.
- Cài gói hệ thống: `sudo dnf install tesseract-langpack-fra tesseract-langpack-chi_sim tesseract-langpack-vie`.
- Hoặc chạy lại `./install.sh`.

**OpenCode AI quá chậm**
- Tăng `ai_timeout_sec` trong cấu hình.
- Kiểm tra `opencode models` và `opencode run --help`.
- Dùng `trans -e ai --no-popup ...` để chỉ lấy bản dịch sạch.

**OSD không hiển thị**
- Kiểm tra GTK4: `python3 -c "import gi; gi.require_version('Gtk','4.0')"`.
- Kiểm tra `libgtk4-layer-shell.so`; SuperTrans tự tìm trong các đường dẫn phổ biến và đặt `LD_PRELOAD` khi chạy OSD.
- Nếu thiếu, SuperTrans tự fallback sang notification.

---

## 📁 Cấu trúc dự án

```
super_trans/
├── cli.py                  # Entry point, thu thập input, chọn engine/output
├── config.py               # Cấu hình mặc định + kiểm tra hợp lệ
├── core/
│   ├── clipboard.py        # PRIMARY/CLIPBOARD, ưu tiên DMS Clipboard
│   ├── detector.py         # Nhận diện Việt/Pháp/Trung, chọn ngôn ngữ đích
│   ├── dms.py              # Lớp tích hợp DMS dùng chung
│   ├── launcher.py         # DMS Launcher, Notepad, thay thế tại chỗ
│   ├── notifier.py         # OSD, DMS toast, notification
│   ├── ocr.py              # Slurp + Grim + Tesseract đa ngôn ngữ
│   └── osd.py              # Thẻ OSD GTK4 Layer Shell
└── engines/
    ├── fast_engine.py      # Google GTX, chia nhỏ văn bản dài
    └── opencode_engine.py  # OpenCode AI: dịch sạch + phân tích
```

---

*SuperTrans được thiết kế để "biến mất" vào hệ thống: bạn chỉ thấy bản dịch xuất hiện đúng nơi mình cần.*
