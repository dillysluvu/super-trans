#!/usr/bin/env bash
# ==============================================================================
# Trình gỡ cài đặt SuperTrans
# ==============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd -P)"
BIN_DIR="$HOME/.local/bin"
NIRI_CONFIG_DIR="$HOME/.config/niri"
NIRI_CONFIG="$NIRI_CONFIG_DIR/config.kdl"
NIRI_TRANS_KDL="$NIRI_CONFIG_DIR/dms/trans.kdl"
CONFIG_DIR="$HOME/.config/super-trans"
CACHE_DIR="$HOME/.cache/super-trans"

PURGE=0
for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=1 ;;
        --help|-h)
            echo "Cách dùng: ./uninstall.sh [--purge]"
            echo "  --purge  Xóa cả cấu hình ~/.config/super-trans và cache phân tích"
            exit 0
            ;;
        *)
            echo "⚠️  Tham số không hợp lệ: $arg" >&2
            exit 2
            ;;
    esac
done

echo "🗑️  Đang gỡ bỏ SuperTrans..."

# 1. Chỉ xóa symlink nếu nó thực sự trỏ tới project này
for link in "$BIN_DIR/super-trans" "$BIN_DIR/trans"; do
    if [ -L "$link" ]; then
        target="$(readlink -f "$link" 2>/dev/null || true)"
        case "$target" in
            "$REAL_SCRIPT_DIR"/*)
                rm -f "$link"
                echo "  ✅ Đã xóa liên kết: $link"
                ;;
            *)
                echo "  ℹ️  Giữ nguyên $link (trỏ tới nơi khác: $target)"
                ;;
        esac
    fi
done

# 2. Xóa phím tắt Niri và include tương ứng
if [ -f "$NIRI_TRANS_KDL" ]; then
    rm -f "$NIRI_TRANS_KDL"
    echo "  ✅ Đã xóa $NIRI_TRANS_KDL."
fi

if [ -f "$NIRI_CONFIG" ]; then
    sed -i '/dms\/trans.kdl/d' "$NIRI_CONFIG"
    echo "  ✅ Đã xóa include khỏi $NIRI_CONFIG."
    if command -v niri >/dev/null 2>&1; then
        niri msg action load-config-file >/dev/null 2>&1 || true
    fi
fi

# 3. Tùy chọn xóa cấu hình và cache
if [ "$PURGE" -eq 1 ]; then
    rm -rf "$CONFIG_DIR" "$CACHE_DIR"
    echo "  ✅ Đã xóa cấu hình và cache phân tích."
else
    echo "  ℹ️  Giữ lại cấu hình tại $CONFIG_DIR (dùng --purge để xóa)."
fi

echo "🎉 Đã hoàn tất gỡ cài đặt SuperTrans."
