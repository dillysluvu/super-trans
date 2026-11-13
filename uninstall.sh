#!/usr/bin/env bash
# ==============================================================================
# Trình gỡ cài đặt SuperTrans
# ==============================================================================

BIN_DIR="$HOME/.local/bin"
NIRI_CONFIG_DIR="$HOME/.config/niri"
NIRI_CONFIG="$NIRI_CONFIG_DIR/config.kdl"
NIRI_TRANS_KDL="$NIRI_CONFIG_DIR/dms/trans.kdl"

echo "🗑️ Đang gỡ bỏ SuperTrans..."

rm -f "$BIN_DIR/super-trans" "$BIN_DIR/trans"
echo "  ✅ Đã xóa liên kết thực thi."

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

echo "🎉 Đã hoàn tất gỡ cài đặt SuperTrans."
