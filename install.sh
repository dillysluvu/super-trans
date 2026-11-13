#!/usr/bin/env bash
# ==============================================================================
# Trình cài đặt SuperTrans - Hệ thống dịch thuật toàn hệ thống
# Hợp tác Antigravity & OpenCode
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
NIRI_CONFIG_DIR="$HOME/.config/niri"
NIRI_CONFIG="$NIRI_CONFIG_DIR/config.kdl"
NIRI_TRANS_KDL="$NIRI_CONFIG_DIR/dms/trans.kdl"

echo "🚀 Bắt đầu thiết lập SuperTrans..."

# 1. Tạo thư mục ~/.local/bin nếu chưa có
mkdir -p "$BIN_DIR"

# 2. Tạo symlink thực thi
chmod +x "$SCRIPT_DIR/bin/super-trans"
ln -sf "$SCRIPT_DIR/bin/super-trans" "$BIN_DIR/super-trans"
ln -sf "$SCRIPT_DIR/bin/super-trans" "$BIN_DIR/trans"
echo "  ✅ Đã liên kết lệnh: $BIN_DIR/super-trans và $BIN_DIR/trans"

# 3. Tạo cấu hình phím tắt cho Niri
mkdir -p "$NIRI_CONFIG_DIR/dms"
cat > "$NIRI_TRANS_KDL" << 'EOF'
// SuperTrans - Siêu tiện ích dịch thuật toàn hệ thống
// Hợp tác phát triển bởi Antigravity AI và OpenCode AI

binds {
    // 🌐 Bôi đen text và nhấn Mod+Alt+T để dịch nhanh (Fast Mode)
    Mod+Alt+T allow-inhibiting=false hotkey-overlay-title="SuperTrans: Dịch text bôi đen" {
        spawn "super-trans" "--selection";
    }

    // 🤖 Bôi đen text và nhấn Mod+Alt+A để dịch chuyên sâu + phân tích AI (OpenCode)
    Mod+Alt+A allow-inhibiting=false hotkey-overlay-title="SuperTrans: Dịch chuyên sâu AI (OpenCode)" {
        spawn "super-trans" "--selection" "--engine" "ai";
    }

    // 📸 Nhấn Mod+Alt+O để kéo chuột chụp vùng ảnh trên màn hình và dịch OCR
    Mod+Alt+O allow-inhibiting=false hotkey-overlay-title="SuperTrans: Chụp vùng màn hình dịch OCR" {
        spawn "super-trans" "--ocr";
    }

    // ⌨️ Nhấn Mod+Alt+I để mở thanh nhập liệu dịch nhanh
    Mod+Alt+I allow-inhibiting=false hotkey-overlay-title="SuperTrans: Hộp thoại nhập liệu dịch nhanh" {
        spawn "super-trans" "--input";
    }
}
EOF
echo "  ✅ Đã tạo file phím tắt Niri: $NIRI_TRANS_KDL"

# 4. Kiểm tra include trong config.kdl
if [ -f "$NIRI_CONFIG" ]; then
    if ! grep -q "dms/trans.kdl" "$NIRI_CONFIG"; then
        echo 'include optional=true "dms/trans.kdl"' >> "$NIRI_CONFIG"
        echo "  ✅ Đã thêm include vào: $NIRI_CONFIG"
    else
        echo "  ℹ️ File $NIRI_CONFIG đã chứa include trans.kdl"
    fi

    # Kiểm tra tính hợp lệ của Niri config
    if command -v niri >/dev/null 2>&1; then
        if niri validate >/dev/null 2>&1; then
            echo "  ✅ Cấu hình Niri hợp lệ!"
            niri msg action load-config-file >/dev/null 2>&1 || true
            echo "  ✅ Đã nạp lại cấu hình Niri thành công!"
        else
            echo "  ⚠️ Cảnh báo: niri validate phát hiện lỗi, vui lòng kiểm tra lại."
        fi
    fi
fi

# 5. Gửi thông báo hoàn tất
notify-send -a "SuperTrans" -i "accessories-dictionary" \
    "🌐 SuperTrans đã sẵn sàng!" \
    "Phím tắt: Mod+Alt+T (Bôi đen), Mod+Alt+A (AI), Mod+Alt+O (OCR), Mod+Alt+I (Nhập)" 2>/dev/null || true

echo ""
echo "🎉 Hoàn tất cài đặt! Bạn có thể sử dụng ngay:"
echo "  - Trong Terminal: trans \"Hello world\" hoặc echo \"text\" | trans"
echo "  - Toàn hệ thống (Phím tắt Niri):"
echo "      * Mod+Alt+T : Bôi đen bất kỳ chữ nào và nhấn để Dịch nhanh tức thì (~150ms)"
echo "      * Mod+Alt+A : Dịch chuyên sâu với OpenCode AI (phân tích thành ngữ, ngữ pháp)"
echo "      * Mod+Alt+O : Chụp vùng màn hình và nhận diện dịch OCR"
echo "      * Mod+Alt+I : Mở ô gõ văn bản dịch nhanh"
