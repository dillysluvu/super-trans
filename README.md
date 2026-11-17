# 🌐 SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống

> **Hợp tác phát triển giữa Antigravity AI và OpenCode AI**, tối ưu hóa riêng cho **Fedora Linux, Niri Wayland Compositor và DMS Shell**.

SuperTrans sống trong hệ thống thay vì mở thêm một cửa sổ rời rạc: bôi đen chữ, nhấn phím tắt, nhận bản dịch ngay trên **Dynamic Island của DMS**, trong Notepad hoặc dán đè trực tiếp tại con trỏ. Giao diện kết quả được tối giản thành hai dòng `gốc : nghĩa` và `engine · ngữ cảnh`. Island **tự mở rộng ngay khi bắt đầu dịch**, hiện `Đang dịch…` rồi cập nhật kết quả tại chỗ nên không có cảm giác chờ đợi. Bản dịch được cache cục bộ, có lịch sử, có thể hoàn tác, và OCR được tăng cường trước khi nhận diện.

---

## ✨ Tính năng chính

### 1. Dịch thuật tích hợp DMS

- **DMS Dynamic Island**: kết quả hiện ngay trên island với bố cục tối giản:
  - tự mở rộng khi bắt đầu dịch, hiện `gốc : Đang dịch…` và icon nhấp nháy;
  - khi có kết quả, cập nhật cùng activity thành `gốc : nghĩa` + `engine · ngữ cảnh`, không thu gọn rồi bung lại;
  - island mở sẵn; phần thân chứa bản dịch đầy đủ, kèm nút **Sao chép** và **Phân tích**; bấm ra ngoài để thu gọn.
- **DMS Launcher / Spotlight (`dms dmenu`)**: phương án dự phòng và vẫn dùng được khi island tắt; kết quả chỉ còn một dòng `gốc : nghĩa` cùng ba hành động ngắn gọn.
- **DMS Notepad**: phân tích chuyên sâu của OpenCode AI được lưu thành Markdown và mở trong Notepad.
- **DMS Clipboard**: bản dịch tự động nằm trong lịch sử clipboard.
- **DMS Toast / Notification**: cũng dùng bố cục `gốc : nghĩa` + `engine · ngữ cảnh`, không lặp lại nhãn ngôn ngữ.
- Cơ chế dự phòng: `island` → `dms dmenu` → `fuzzel`, `dms clipboard` → `wl-copy` + `wtype`, `dms notify` → `notify-send`, DMS Notepad → `xdg-open`.

### 2. Thay thế tại chỗ an toàn + Hoàn tác

- Bôi đen câu tiếng Anh/Pháp/Trung → `Mod+Alt+R` → văn bản được dịch và dán đè ngay tại con trỏ, không mở cửa sổ.
- Tự nhận biết terminal để dùng `Ctrl+Shift+V` thay vì `Ctrl+V`.
- **Chỉ dùng PRIMARY selection** cho `--replace`, tránh dán nhầm clipboard cũ. Muốn dùng clipboard, phải chỉ định rõ `--clipboard`.
- **Lưu lần thay thế gần nhất** vào SQLite. `trans --undo` (hoặc `Mod+Alt+Z`) gửi `Ctrl+Z` để khôi phục; nếu cửa sổ đang focus khác cửa sổ đã thay thế, SuperTrans từ chối để tránh undo nhầm.
- Trong **terminal**, SuperTrans không gửi `Ctrl+Z` (vì đó là tín hiệu tạm dừng tiến trình) mà sao chép bản gốc vào clipboard để bạn dán thủ công bằng `Ctrl+Shift+V`.

### 3. Cache & lịch sử SQLite

- Cache bản dịch theo `(văn bản, ngôn ngữ nguồn, ngôn ngữ đích, engine)`.
- Lặp lại cùng một câu sẽ trả kết quả tức thì, không gọi mạng.
- Lưu lịch sử để xem, tìm kiếm, thống kê và dọn dẹp.
- Dữ liệu nằm trong `~/.local/share/super-trans/history.db`, quyền `0600`, không gửi đi đâu cả.
- Tắt cache cho một lần chạy bằng `--no-cache`; buộc dịch lại bằng `--refresh`.

### 4. OCR mạnh hơn

- Chụp vùng màn hình bằng `slurp` + `grim`, nhận diện bằng Tesseract.
- **Tăng cường ảnh** trước OCR: chuyển xám, tự đảo màu cho dark mode, cân bằng tương phản, làm nét, phóng to ảnh nhỏ và thêm viền trắng.
- Hỗ trợ OCR **file ảnh có sẵn** (`--ocr-file`) và **ảnh trong clipboard** (`--ocr-clipboard`).
- Tự chọn thư mục `tessdata` có nhiều ngôn ngữ nhất và lọc bỏ gói chưa cài.
- Hỗ trợ tiếng Anh, Pháp, Trung giản thể, Việt.

### 5. Helper Rust tùy chọn

- Helper `super-trans-native` chia văn bản rất dài thành đoạn trước khi gửi dịch.
- Helper còn nói chuyện **trực tiếp với Unix socket của Quickshell/DMS** để publish, mở rộng, xóa activity và poll nút bấm — không spawn tiến trình `dms` cho mỗi thao tác.
- Watcher Rust poll mỗi ~80 ms, nên nút **Sao chép / Phân tích** phản hồi nhanh hơn hẳn vòng poll Python cũ.
- Build tự động nếu máy có `cargo`; nếu không, SuperTrans dùng Python/DMS CLI và mọi tính năng vẫn hoạt động.
- **Lưu ý hiệu năng:** độ trễ dịch chủ yếu đến từ mạng (Google GTX) và Tesseract. Rust giúp phần chia văn bản lớn và thao tác island mượt hơn, không làm bản thân bản dịch nhanh hơn.

---

## 📋 Yêu cầu hệ thống

| Thành phần | Vai trò | Ghi chú |
|---|---|---|
| `python3` | Chạy SuperTrans | Bắt buộc (>= 3.9) |
| `wl-clipboard` (`wl-paste`, `wl-copy`) | Đọc/ghi clipboard, PRIMARY | Khuyến nghị |
| `wtype` | Dự phòng dán tại chỗ và gửi `Ctrl+Z` | Khuyến nghị |
| `slurp`, `grim`, `tesseract` | OCR vùng màn hình | Cần cho `--ocr` |
| `dms` | Dynamic Island, Launcher, Notepad, Clipboard, Toast | Tùy chọn, có fallback |
| `fuzzel` | Fallback Launcher | Tùy chọn |
| `opencode` | Engine AI | Cần cho `-e ai` |
| Pillow hoặc ImageMagick | Tăng cường ảnh OCR | Tùy chọn, khuyến nghị |
| `cargo` | Build helper Rust (kèm IPC island) | Tùy chọn |
| GTK4 + `gtk4-layer-shell` | Thẻ OSD nổi | Tùy chọn cho `--output osd` |

Cài đặt gói cơ bản trên Fedora:

```bash
sudo dnf install python3 wl-clipboard wtype slurp grim tesseract
sudo dnf install python3-pillow   # khuyến nghị cho OCR
```

---

## 🚀 Cài đặt

```bash
git clone https://github.com/dillysluvu/super-trans.git ~/trans
cd ~/trans
./install.sh
```

Trình cài đặt sẽ:

- Liên kết lệnh `super-trans` và `trans` vào `~/.local/bin`.
- Build helper Rust (chia văn bản + IPC island) vào `~/.local/lib/super-trans/super-trans-native` nếu có `cargo`.
- Tải các gói OCR `fra`, `chi_sim`, `vie` vào `~/.local/share/tessdata` (nếu thiếu).
- Tạo phím tắt Niri tại `~/.config/niri/dms/trans.kdl` và thêm include vào `config.kdl`.
- Nạp lại cấu hình Niri nếu `niri validate` thành công.

Chỉ cài CLI, không tạo phím tắt Niri:

```bash
./install.sh --no-niri
```

Cài như một gói Python (tùy chọn, dùng pipx):

```bash
pipx install .            # CLI + OCR cơ bản
pipx install '.[ocr]'     # kèm Pillow để tăng cường ảnh
```

Gỡ cài đặt:

```bash
./uninstall.sh          # Giữ cấu hình và lịch sử
./uninstall.sh --purge  # Xóa cả cấu hình, cache và lịch sử SQLite
```

---

## ⌨️ Phím tắt toàn hệ thống (Niri Wayland)

| Phím tắt | Chức năng | Cơ chế hoạt động |
|---|---|---|
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> | **Dịch trên Dynamic Island** | Bôi đen text → island tự mở rộng, hiện `Đang dịch…` rồi cập nhật `gốc : nghĩa` + `engine · ngữ cảnh`; phần thân chứa bản dịch đầy đủ. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>R</kbd> | **Thay thế trực tiếp tại chỗ** | Bôi đen text → dịch và dán đè, không hiện thông báo. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>Z</kbd> | **Hoàn tác thay thế gần nhất** | Gửi `Ctrl+Z` tới cửa sổ đã thay thế. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> | **Phân tích chuyên sâu** | OpenCode AI phân tích thành ngữ, ngữ pháp, sắc thái trong DMS Notepad. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>O</kbd> | **OCR vùng màn hình** | Kéo chuột quét ảnh/video → kết quả trên Dynamic Island. |
| <kbd>Mod</kbd> + <kbd>Alt</kbd> + <kbd>I</kbd> | **Hộp thoại nhập liệu nhanh** | Mở thanh nhập liệu → kết quả trên Dynamic Island. |

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

# Thay thế văn bản đang bôi đen (chỉ PRIMARY)
trans --replace
trans -r

# Thay thế từ clipboard (chỉ định rõ)
trans --replace --clipboard

# Hoàn tác lần thay thế gần nhất
trans --undo
trans --undo --force

# Mở kết quả tối giản trên Dynamic Island (mặc định mới)
trans --selection --output island
trans --output island "Hello"

# Mở kết quả trong DMS Launcher (dự phòng / cần menu hành động)
trans --selection --output launcher

# Phân tích chuyên sâu bằng OpenCode AI (mở DMS Notepad)
trans -e ai "塞翁失马"

# AI trả kết quả tối giản trên island, kèm một dòng ngữ cảnh
trans -e ai --output island "Break a leg"

# Chỉ lấy bản dịch sạch, không mở Notepad
trans -e ai --no-popup "塞翁失马"
trans -e ai --output none "塞翁失马"

# OCR vùng màn hình, file ảnh hoặc clipboard
trans --ocr
trans --ocr --ocr-lang "eng+vie"
trans --ocr-file screenshot.png
trans --ocr-clipboard
trans --ocr-file scan.png --no-ocr-preprocess

# Lịch sử, tìm kiếm, thống kê
trans --history
trans --history 30
trans --search "thank you"
trans --stats

# Bỏ qua cache hoặc buộc dịch lại
trans --no-cache "Hello"
trans --refresh "Hello"

# Dọn dẹp và chẩn đoán
trans --clear-history --yes
trans --doctor
```

### Các tùy chọn chính

| Tùy chọn | Mô tả |
|---|---|
| `-s`, `--selection` | Lấy văn bản đang bôi đen (PRIMARY) hoặc clipboard. |
| `--clipboard` | Dùng clipboard làm nguồn; bắt buộc nếu muốn `--replace` từ clipboard. |
| `-r`, `--replace` | Dịch và thay thế trực tiếp tại vị trí con trỏ. |
| `-o`, `--ocr` | Kéo chuột chụp vùng màn hình và OCR. |
| `--ocr-file PATH` | OCR một file ảnh có sẵn. |
| `--ocr-clipboard` | OCR ảnh đang có trong clipboard. |
| `--ocr-lang` | Ghi đè ngôn ngữ Tesseract, ví dụ `eng+fra+chi_sim+vie`. |
| `--ocr-psm` | Page Segmentation Mode của Tesseract (0–13). |
| `--ocr-preprocess` / `--no-ocr-preprocess` | Bật/tắt tăng cường ảnh cho lần chạy. |
| `-i`, `--input` | Mở ô nhập liệu nhanh qua DMS Launcher. |
| `-e`, `--engine` | `fast` (Google GTX) hoặc `ai` (OpenCode). |
| `-m`, `--output` | `island`, `launcher`, `replace`, `osd`, `dms_toast`, `notification`, `none`. |
| `--from`, `--to` | Chỉ định ngôn ngữ nguồn/đích. |
| `--no-copy` | Không tự động sao chép kết quả vào clipboard. |
| `--no-popup` | Không mở DMS Notepad khi dùng engine AI. |
| `--no-cache` | Không đọc/ghi cache cho lần dịch này. |
| `--refresh` | Bỏ qua cache, dịch lại rồi cập nhật cache. |
| `--history [N]` | Xem N bản dịch gần nhất (mặc định 15). |
| `--search TỪ` | Tìm trong lịch sử. |
| `--stats` | Thống kê cache/lịch sử. |
| `--clear-history --yes` | Xóa toàn bộ lịch sử và cache. |
| `--undo` | Hoàn tác lần thay thế gần nhất. |
| `--force` | Cho phép undo dù cửa sổ đang focus khác. |
| `--doctor` | Kiểm tra phụ thuộc, OCR, cache và helper Rust. |
| `--verbose` | In thông tin chẩn đoán ra stderr. |

---

## ⚙️ Cấu hình

File cấu hình: `~/.config/super-trans/config.json`

```json
{
  "default_engine": "fast",
  "output_mode": "island",
  "ai_model": "opencode/deepseek-v4.1-flash-free",
  "ai_timeout_sec": 120,
  "primary_target_lang": "vi",
  "secondary_target_lang": "en",
  "auto_copy_to_clipboard": true,
  "notification_timeout_ms": 6000,
  "island_timeout_ms": 10000,
  "show_popup_on_ai": true,
  "ocr_lang": "eng+fra+chi_sim+vie",
  "ocr_preprocess": true,
  "ocr_psm": 3,
  "cache_enabled": true,
  "history_limit": 500
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
| `notification_timeout_ms` | Thời gian hiển thị toast/notification (1–60 giây). |
| `island_timeout_ms` | Thời gian hiển thị kết quả trên Dynamic Island (2–60 giây). |
| `show_popup_on_ai` | Mở DMS Notepad khi dùng engine AI. |
| `ocr_lang` | Danh sách ngôn ngữ Tesseract mặc định. |
| `ocr_preprocess` | Bật tăng cường ảnh trước OCR. |
| `ocr_psm` | Page Segmentation Mode mặc định (0–13). |
| `cache_enabled` | Bật cache + lịch sử SQLite. |
| `history_limit` | Số mục lịch sử tối đa giữ lại (10–10000). |

Giá trị `output_mode`:

- `island`: Dynamic Island của DMS (mặc định), bố cục `gốc : nghĩa` + `engine · ngữ cảnh`; fallback Launcher nếu island không khả dụng.
- `launcher`: DMS Spotlight Launcher, fallback `fuzzel`.
- `replace`: Thay thế tại chỗ bằng DMS Clipboard/wtype.
- `osd`: Thẻ Wayland OSD nổi (GTK4 + Layer Shell).
- `dms_toast`: Toast trên Dynamic Island của DMS (một dòng kết quả + ngữ cảnh).
- `notification`: Notification desktop.
- `none`: Chỉ in ra stdout.

Với `island`, SuperTrans publish ngay một activity `Đang dịch…` và gọi `islandActivity open` để mở rộng trước khi gọi mạng/AI. Khi có kết quả, cùng source/id được cập nhật tại chỗ, giữ trạng thái mở rộng; phần thân hiển thị bản dịch đầy đủ. Hai nút **Sao chép** và **Phân tích** được xử lý bởi tiến trình nền nhỏ (watcher Rust khi có helper) và tự thoát khi island đóng. Nếu DMS tắt activity hoặc không chạy, SuperTrans tự quay về Launcher để không mất thao tác.

---

## 💾 Cache, lịch sử và quyền riêng tư

- Database: `~/.local/share/super-trans/history.db` (SQLite, chmod `0600`).
- Bảng `translations`: cache + lịch sử bản dịch.
- Bảng `replacements`: lần thay thế gần nhất và trạng thái hoàn tác.
- Cache key gồm văn bản gốc, ngôn ngữ nguồn/đích và engine (với AI là model cụ thể).
- Lịch sử lưu **văn bản gốc dạng plaintext** để bạn có thể tìm kiếm. Nếu dịch nội dung nhạy cảm:
  - Dùng `--no-cache` cho lần dịch đó, hoặc
  - Đặt `"cache_enabled": false`, hoặc
  - Chạy `trans --clear-history --yes` sau khi dùng.
- Cache tự dọn bớt theo `history_limit`; không có dữ liệu nào được gửi lên máy chủ nào ngoài engine dịch bạn chọn.

---

## 🧠 Cách hoạt động của engine AI

- `trans -e ai "..."` gọi OpenCode với prompt yêu cầu **bản dịch sạch** và **phân tích Markdown**.
- Bài phân tích được lưu tại `~/.cache/super-trans/super-trans-analysis-*.md` và mở trong DMS Notepad.
- Mặc định, khi Notepad đã mở, SuperTrans **không mở thêm island/Launcher** để tránh trùng lặp.
- Nếu chỉ định rõ `--output` (ví dụ `--output island` hoặc `--output launcher`), SuperTrans dùng bản dịch sạch, bỏ qua Notepad; với island, dòng đầu phần phân tích được dùng làm ngữ cảnh.
- Nếu OpenCode lỗi hoặc quá thời gian, SuperTrans tự chuyển sang FastEngine và báo lỗi ra stderr.
- Bản dịch AI sạch cũng được cache; lần sau `-e ai --no-popup` có thể trả ngay từ cache.

---

## 🔍 OCR đa ngôn ngữ

- `install.sh` tự tải `fra`, `chi_sim`, `vie` (và `eng` nếu chưa có) vào `~/.local/share/tessdata`.
- SuperTrans tự chọn thư mục tessdata có nhiều ngôn ngữ nhất và **lọc bỏ ngôn ngữ chưa cài** thay vì để Tesseract báo lỗi.
- Ảnh đầu vào được tăng cường bằng Pillow (ưu tiên) hoặc ImageMagick:
  - ảnh xám, đảo màu cho dark mode, autocontrast, unsharp mask, phóng to ảnh nhỏ, viền trắng.
- Ba chế độ đầu vào: vùng màn hình (`--ocr`), file (`--ocr-file`), clipboard (`--ocr-clipboard`).
- Nhấn `Esc` khi chọn vùng để hủy mà không báo lỗi.
- Ảnh tạm được xóa ngay sau khi OCR.

---

## 🦀 Helper Rust (tùy chọn)

```bash
# Build thủ công
cargo build --release --manifest-path native/Cargo.toml

# Kiểm tra SuperTrans nhận helper chưa
trans --doctor
```

Helper có hai nhiệm vụ:

1. **Chia văn bản dài** thành đoạn ≤ giới hạn, ưu tiên xuống dòng → cuối câu → khoảng trắng → cắt cứng. Python tự dùng helper khi văn bản ≥ 4000 ký tự và kiểm tra lại để không mất nội dung.
2. **IPC Dynamic Island trực tiếp**: kết nối Unix socket của Quickshell để `publish`, `open`, `remove` và `pollActions`. Watcher Rust poll ~80 ms, phát JSON line cho tiến trình Python xử lý nút bấm. Nhờ vậy không phải spawn `dms` mỗi vòng poll.

- Nếu helper chưa build, phiên bản cũ, hoặc socket không khả dụng, SuperTrans tự quay về DMS CLI + vòng poll Python.
- `serde_json` được dùng để parse payload/action trong Rust.
- Kiểm tra helper nhận đúng chưa: `trans --doctor` sẽ hiện **Rust IPC island — Quickshell socket trực tiếp**.
- **Không kỳ vọng Rust làm dịch nhanh hơn đáng kể**: thời gian chủ yếu nằm ở request mạng và OCR. Rust cải thiện độ mượt của island và phản hồi nút bấm.

---

## 🧪 Kiểm thử

```bash
# Toàn bộ kiểm thử offline (mock mạng, DB tạm)
python3 -m unittest discover -s tests -v

# Kiểm thử tích hợp thật với Google Translate
SUPERTRANS_LIVE_TESTS=1 python3 -m unittest discover -s tests -v

# Kiểm thử helper Rust (nếu có cargo)
cargo test --manifest-path native/Cargo.toml
```

Bộ kiểm thử bao quát: nhận diện Việt/Pháp/Trung, chia nhỏ văn bản dài (Python + Rust), parse phản hồi dịch, retry mạng, lọc ngôn ngữ OCR, trạng thái DMS dmenu, payload Dynamic Island (kể cả trạng thái `Đang dịch…` và auto-expand), IPC Rust, xử lý nút Sao chép/Phân tích, cache/lịch sử SQLite, undo, an toàn PRIMARY/clipboard, tăng cường ảnh, và logic tránh mở trùng Notepad + island/Launcher.

---

## 🛠️ Khắc phục sự cố

**Không thấy kết quả trên Dynamic Island**
- Kiểm tra `dms ipc call islandActivity availability` trả về `"islandPresent": true` và `"activitiesAvailable": true`.
- Bật activity/island trong cài đặt DMS nếu đang tắt.
- Island tự mở rộng bằng `dms ipc call islandActivity open <source> <id>`; kiểm tra `dms ipc call island status` thấy `"expanded":true`.
- Nếu helper Rust cũ, chạy lại `./install.sh` hoặc `cargo build --release --manifest-path native/Cargo.toml` rồi cài bản mới; `trans --doctor` phải hiện **Rust IPC island**.
- SuperTrans sẽ tự fallback sang DMS Launcher rồi `fuzzel` nếu island không phản hồi.
- Chạy `trans --doctor` để xem mục **Dynamic Island**.
- Nếu chỉ muốn kiểm tra nhanh: `trans --output island "Hello"`.

**Không thấy kết quả trong DMS Launcher**
- Kiểm tra `dms ipc call toast status` trả về trạng thái hợp lệ.
- SuperTrans sẽ tự fallback sang `fuzzel` nếu DMS shell không phản hồi.
- Nếu cả hai đều không có, dùng `trans --output notification "..."`.

**Phím tắt không hoạt động**
- Kiểm tra `~/.config/niri/config.kdl` có dòng `include optional=true "dms/trans.kdl"`.
- Chạy `niri validate` và `niri msg action load-config-file`.
- Đảm bảo `~/.local/bin` nằm trong `PATH` của phiên Niri.

**`--replace` báo không tìm thấy vùng bôi đen**
- SuperTrans cố ý không dùng clipboard cũ cho `--replace`.
- Bôi đen lại văn bản, hoặc dùng `trans --replace --clipboard` nếu chắc chắn.
- Nếu terminal dùng app_id lạ, thêm tên vào `TERMINAL_APP_IDS` trong `super_trans/core/launcher.py`.

**Undo không hoạt động**
- Undo gửi `Ctrl+Z` qua `wtype`; kiểm tra `command -v wtype`.
- Nếu cửa sổ đang focus khác cửa sổ đã thay thế, dùng `trans --undo --force`.
- Trong terminal, SuperTrans **cố ý không gửi `Ctrl+Z`** (sẽ tạm dừng tiến trình) mà copy bản gốc vào clipboard; hãy dán bằng `Ctrl+Shift+V`.
- Ứng dụng không hỗ trợ undo sẽ không khôi phục được; khi đó SuperTrans đã sao chép bản gốc vào clipboard để dán thủ công.

**OCR báo thiếu ngôn ngữ**
- Kiểm tra `ls ~/.local/share/tessdata`.
- Cài gói hệ thống: `sudo dnf install tesseract-langpack-fra tesseract-langpack-chi_sim tesseract-langpack-vie`.
- Hoặc chạy lại `./install.sh`.

**OCR nhận sai chữ**
- Thử `trans --ocr --no-ocr-preprocess` nếu ảnh đã sạch.
- Thử `--ocr-psm 6` cho khối văn bản liền, `--ocr-psm 7` cho một dòng.
- Cài Pillow để có tăng cường ảnh tốt hơn: `sudo dnf install python3-pillow`.

**OpenCode AI quá chậm**
- Tăng `ai_timeout_sec` trong cấu hình.
- Kiểm tra `opencode models` và `opencode run --help`.
- Dùng `trans -e ai --no-popup ...` để chỉ lấy bản dịch sạch.

**OSD không hiển thị**
- Kiểm tra GTK4: `python3 -c "import gi; gi.require_version('Gtk','4.0')"`.
- Kiểm tra `libgtk4-layer-shell.so`; SuperTrans tự tìm trong các đường dẫn phổ biến và đặt `LD_PRELOAD` khi chạy OSD.
- Nếu thiếu, SuperTrans tự fallback sang notification.

**Muốn kiểm tra toàn bộ hệ thống**
```bash
trans --doctor
```

---

## 📁 Cấu trúc dự án

```
super_trans/
├── cli.py                  # Entry point, CLI, cache, lịch sử, doctor
├── config.py               # Cấu hình mặc định + kiểm tra hợp lệ
├── core/
│   ├── clipboard.py        # PRIMARY/CLIPBOARD, ưu tiên DMS Clipboard
│   ├── detector.py         # Nhận diện Việt/Pháp/Trung, chọn ngôn ngữ đích
│   ├── dms.py              # Lớp tích hợp DMS dùng chung
│   ├── image_prep.py       # Tăng cường ảnh OCR (Pillow/ImageMagick)
│   ├── island.py           # Publish kết quả tối giản lên DMS Dynamic Island
│   ├── island_watch.py     # Tiến trình nền xử lý nút Sao chép/Phân tích
│   ├── launcher.py         # DMS Launcher, Notepad, thay thế, undo
│   ├── native.py           # Cầu nối helper Rust + fallback Python
│   ├── notifier.py         # Island, OSD, DMS toast, notification
│   ├── ocr.py              # Slurp + Grim + Tesseract, file/clipboard
│   ├── osd.py              # Thẻ OSD GTK4 Layer Shell
│   ├── presentation.py     # Định dạng `gốc : nghĩa`, `engine · ngữ cảnh`
│   └── store.py            # SQLite cache, lịch sử, nhật ký thay thế
├── engines/
│   ├── fast_engine.py      # Google GTX, chia nhỏ văn bản dài
│   └── opencode_engine.py  # OpenCode AI: dịch sạch + phân tích
native/
├── Cargo.toml
└── src/
    ├── main.rs             # Helper Rust: chia văn bản dài
    └── island.rs           # IPC Quickshell + watcher Dynamic Island
tests/
└── test_super_trans.py
```

---

## 📄 Giấy phép

MIT License. Xem [LICENSE](LICENSE).

---

*SuperTrans được thiết kế để "biến mất" vào hệ thống: bạn chỉ thấy bản dịch xuất hiện đúng nơi mình cần.*
