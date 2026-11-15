#!/usr/bin/env bash
# ==============================================================================
# Trình cài đặt SuperTrans - Hệ thống dịch thuật toàn hệ thống
# Hợp tác Antigravity & OpenCode
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
NIRI_CONFIG_DIR="$HOME/.config/niri"
NIRI_CONFIG="$NIRI_CONFIG_DIR/config.kdl"
NIRI_TRANS_KDL="$NIRI_CONFIG_DIR/dms/trans.kdl"
TESSDATA_DIR="$HOME/.local/share/tessdata"

INSTALL_NIRI=1
for arg in "$@"; do
    case "$arg" in
        --no-niri) INSTALL_NIRI=0 ;;
        --help|-h)
            echo "Cách dùng: ./install.sh [--no-niri]"
            echo "  --no-niri  Không tạo phím tắt Niri (chỉ cài CLI + OCR)"
            exit 0
            ;;
        *)
            echo "⚠️  Tham số không hợp lệ: $arg" >&2
            exit 2
            ;;
    esac
done

echo "🚀 Bắt đầu thiết lập SuperTrans..."

# 0. Kiểm tra phụ thuộc
MISSING=()
for cmd in python3 wl-copy wtype slurp grim tesseract; do
    command -v "$cmd" >/dev/null 2>&1 || MISSING+=("$cmd")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "  ⚠️  Thiếu công cụ: ${MISSING[*]}"
    echo "     Cài trên Fedora: sudo dnf install wl-clipboard wtype slurp grim tesseract"
    echo "     (CLI vẫn cài được, nhưng một số tính năng sẽ không hoạt động.)"
fi
if ! command -v dms >/dev/null 2>&1; then
    echo "  ℹ️  Không thấy DMS CLI — sẽ dùng fuzzel/notify-send làm phương án dự phòng."
fi

# 1. Tạo thư mục ~/.local/bin và liên kết thực thi
mkdir -p "$BIN_DIR"
chmod +x "$SCRIPT_DIR/bin/super-trans" "$SCRIPT_DIR/install.sh" "$SCRIPT_DIR/uninstall.sh"
ln -sfn "$SCRIPT_DIR/bin/super-trans" "$BIN_DIR/super-trans"
ln -sfn "$SCRIPT_DIR/bin/super-trans" "$BIN_DIR/trans"
echo "  ✅ Đã liên kết lệnh: $BIN_DIR/super-trans và $BIN_DIR/trans"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "  ⚠️  $BIN_DIR chưa có trong PATH. Thêm dòng sau vào ~/.zshrc hoặc ~/.bashrc:"
       echo '       export PATH="$HOME/.local/bin:$PATH"' ;;
esac

# 2. Cài đặt gói OCR đa ngôn ngữ (Anh, Pháp, Trung, Việt)
mkdir -p "$TESSDATA_DIR"

# Liên kết gói tiếng Anh có sẵn của hệ thống (Fedora/Debian)
if [ ! -f "$TESSDATA_DIR/eng.traineddata" ]; then
    for src in \
        "/usr/share/tesseract/tessdata/eng.traineddata" \
        "/usr/share/tesseract-ocr/5/tessdata/eng.traineddata" \
        "/usr/share/tesseract-ocr/4.00/tessdata/eng.traineddata"; do
        if [ -f "$src" ]; then
            ln -sfn "$src" "$TESSDATA_DIR/eng.traineddata"
            break
        fi
    done
fi

for lang in eng fra chi_sim vie; do
    target="$TESSDATA_DIR/${lang}.traineddata"
    if [ ! -s "$target" ]; then
        rm -f "$target"
        echo "  📥 Đang tải gói OCR ${lang}..."
        tmp_file="${target}.part"
        if curl --fail --location --retry 2 --silent --show-error \
            -o "$tmp_file" \
            "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/${lang}.traineddata" \
            && [ "$(wc -c < "$tmp_file")" -gt 1000 ]; then
            mv "$tmp_file" "$target"
        else
            rm -f "$tmp_file"
            echo "  ⚠️  Không tải được gói OCR ${lang} (kiểm tra mạng hoặc cài tesseract-langpack-${lang})."
        fi
    fi
done
echo "  ✅ Đã sẵn sàng OCR cho Tiếng Anh, Pháp, Trung, Việt"

# 3. Tạo cấu hình phím tắt cho Niri
if [ "$INSTALL_NIRI" -eq 1 ]; then
    mkdir -p "$NIRI_CONFIG_DIR/dms"
    cat > "$NIRI_TRANS_KDL" << 'EOF'
// SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống
// Hợp tác phát triển bởi Antigravity AI và OpenCode AI
// Tích hợp 100% vào các tiện ích có sẵn của hệ thống (DMS Launcher, DMS Notepad, wtype)

binds {
    // 🌐 Bôi đen text và nhấn Mod+Alt+T để xem bản dịch trong DMS Launcher (Spotlight)
    Mod+Alt+T allow-inhibiting=false hotkey-overlay-title="SuperTrans: Xem bản dịch trong DMS Launcher" {
        spawn "super-trans" "--selection" "--output" "launcher";
    }

    // ✍️ Bôi đen text và nhấn Mod+Alt+R để THAY THẾ TRỰC TIẾP tại chỗ (In-place replace)
    Mod+Alt+R allow-inhibiting=false hotkey-overlay-title="SuperTrans: Thay thế văn bản tại chỗ (In-place)" {
        spawn "super-trans" "--replace";
    }

    // 🤖 Bôi đen text và nhấn Mod+Alt+A để phân tích chuyên sâu OpenCode AI trong DMS Notepad
    Mod+Alt+A allow-inhibiting=false hotkey-overlay-title="SuperTrans: Phân tích AI trong DMS Notepad" {
        spawn "super-trans" "--selection" "--engine" "ai";
    }

    // 📸 Nhấn Mod+Alt+O để kéo chuột chụp vùng ảnh màn hình OCR và mở trong DMS Launcher
    Mod+Alt+O allow-inhibiting=false hotkey-overlay-title="SuperTrans: Chụp vùng màn hình OCR" {
        spawn "super-trans" "--ocr" "--output" "launcher";
    }

    // ⌨️ Nhấn Mod+Alt+I để mở thanh nhập liệu dịch nhanh bằng DMS Launcher
    Mod+Alt+I allow-inhibiting=false hotkey-overlay-title="SuperTrans: Ô nhập liệu dịch DMS Launcher" {
        spawn "super-trans" "--input";
    }
}
EOF
    echo "  ✅ Đã tạo file phím tắt Niri: $NIRI_TRANS_KDL"

    # 4. Kiểm tra include trong config.kdl
    if [ -f "$NIRI_CONFIG" ]; then
        if ! grep -q "dms/trans.kdl" "$NIRI_CONFIG"; then
            # Đảm bảo file kết thúc bằng newline trước khi nối thêm include
            if [ -n "$(tail -c 1 "$NIRI_CONFIG" 2>/dev/null || true)" ]; then
                echo >> "$NIRI_CONFIG"
            fi
            echo 'include optional=true "dms/trans.kdl"' >> "$NIRI_CONFIG"
            echo "  ✅ Đã thêm include vào: $NIRI_CONFIG"
        else
            echo "  ℹ️  File $NIRI_CONFIG đã chứa include trans.kdl"
        fi

        # Kiểm tra tính hợp lệ của Niri config
        if command -v niri >/dev/null 2>&1; then
            if niri validate >/dev/null 2>&1; then
                echo "  ✅ Cấu hình Niri hợp lệ!"
                niri msg action load-config-file >/dev/null 2>&1 || true
                echo "  ✅ Đã nạp lại cấu hình Niri thành công!"
            else
                echo "  ⚠️  Cảnh báo: niri validate phát hiện lỗi, vui lòng kiểm tra lại."
            fi
        fi
    else
        echo "  ⚠️  Không tìm thấy $NIRI_CONFIG — bỏ qua bước thêm include."
    fi
fi

# 5. Gửi thông báo hoàn tất
if command -v dms >/dev/null 2>&1; then
    timeout 3 dms notify -a "SuperTrans" -i "accessories-dictionary" \
        "🌐 SuperTrans đã sẵn sàng!" \
        "Phím tắt: Mod+Alt+T (Bôi đen), Mod+Alt+A (AI), Mod+Alt+O (OCR), Mod+Alt+I (Nhập)" \
        >/dev/null 2>&1 || true
elif command -v notify-send >/dev/null 2>&1; then
    notify-send -a "SuperTrans" -i "accessories-dictionary" \
        "🌐 SuperTrans đã sẵn sàng!" \
        "Phím tắt: Mod+Alt+T (Bôi đen), Mod+Alt+A (AI), Mod+Alt+O (OCR), Mod+Alt+I (Nhập)" \
        2>/dev/null || true
fi

echo ""
echo "🎉 Hoàn tất cài đặt! Bạn có thể sử dụng ngay:"
echo "  - Trong Terminal: trans \"Hello world\" hoặc echo \"text\" | trans"
if [ "$INSTALL_NIRI" -eq 1 ]; then
    echo "  - Toàn hệ thống (Phím tắt Niri):"
    echo "      * Mod+Alt+T : Bôi đen chữ và dịch nhanh trong DMS Launcher (~150ms)"
    echo "      * Mod+Alt+R : Dịch và thay thế trực tiếp tại chỗ (không cửa sổ)"
    echo "      * Mod+Alt+A : Phân tích chuyên sâu bằng OpenCode AI trong DMS Notepad"
    echo "      * Mod+Alt+O : Chụp vùng màn hình và dịch OCR"
    echo "      * Mod+Alt+I : Mở ô nhập văn bản cần dịch"
fi
