"""
SuperTrans Floating OSD Card (GTK4 + Layer Shell)
Giao diện hiển thị kết quả dịch nổi tối giản, chuẩn Wayland, đồng nhất với Niri & DMS.
"""

import sys
import os
import argparse
import subprocess
import shutil

def run_osd_app(original: str, translated: str, src_lang: str, tgt_lang: str,
                engine: str, timeout_sec: float = 6.0):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    
    use_layer_shell = False
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell
        use_layer_shell = True
    except Exception:
        pass

    from gi.repository import Gtk, Gdk, GLib

    app = Gtk.Application(application_id="dev.supertrans.osd.popup")

    def on_activate(app):
        win = Gtk.ApplicationWindow(application=app)
        win.set_title("SuperTrans")

        # 1. Cấu hình Wayland Layer Shell
        if use_layer_shell:
            Gtk4LayerShell.init_for_window(win)
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_namespace(win, "super-trans")
            Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.RIGHT, True)
            Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.TOP, 24)
            Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.RIGHT, 24)
            Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.ON_DEMAND)
        else:
            win.set_default_size(420, 200)

        # 2. Áp dụng CSS Styling đồng bộ theme Niri / DMS (#1a6265)
        css_data = b"""
        @define-color st_accent #1a6265;
        @define-color st_accent_soft rgba(26, 98, 101, 0.22);
        @define-color st_card_bg rgba(18, 22, 23, 0.93);
        @define-color st_border rgba(26, 98, 101, 0.85);

        .osd-card {
            background-color: @st_card_bg;
            color: #e5ecec;
            border: 1.5px solid @st_border;
            border-radius: 14px;
            padding: 14px 18px;
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.55);
            min-width: 360px;
        }

        .osd-header {
            margin-bottom: 6px;
        }

        .osd-badge {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.05em;
            padding: 2px 10px;
            border-radius: 999px;
            color: #3fd3d8;
            background-color: @st_accent_soft;
            border: 1px solid rgba(63, 211, 216, 0.3);
        }

        .osd-engine {
            font-size: 11px;
            color: #92a4a4;
            margin-left: 8px;
        }

        .osd-keycap {
            font-size: 10px;
            font-weight: 600;
            padding: 1px 7px;
            border-radius: 5px;
            color: #8da1a1;
            background-color: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .osd-src {
            font-size: 12px;
            color: #889999;
            margin: 4px 0 6px 0;
            line-height: 1.35;
        }

        .osd-rule {
            background-color: rgba(255, 255, 255, 0.10);
            min-height: 1px;
            margin: 4px 0 8px 0;
        }

        .osd-dst {
            font-size: 14.5px;
            font-weight: 500;
            color: #ffffff;
            line-height: 1.5;
        }

        .osd-scroll {
            min-height: 20px;
        }

        .osd-foot {
            margin-top: 10px;
        }

        .osd-hint {
            font-size: 10.5px;
            color: #728484;
        }

        .osd-hint-copied {
            font-size: 11px;
            font-weight: 600;
            color: #3fd3d8;
        }

        .osd-bar-bg {
            background-color: rgba(255, 255, 255, 0.08);
            border-radius: 2px;
            min-height: 2px;
            margin-top: 6px;
        }

        .osd-progress {
            background-color: #3fd3d8;
            border-radius: 2px;
            min-height: 2px;
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css_data)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # 3. Tạo layout các phần tử UI
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.add_css_class("osd-card")

        # Header: [NGÔN NGỮ] [Engine] ... [Esc]
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.add_css_class("osd-header")

        badge_label = Gtk.Label(label=f"{src_lang.upper()} ➔ {tgt_lang.upper()}")
        badge_label.add_css_class("osd-badge")
        header_box.append(badge_label)

        engine_label = Gtk.Label(label=f"• {engine}")
        engine_label.add_css_class("osd-engine")
        header_box.append(engine_label)

        spacer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        spacer.set_hexpand(True)
        header_box.append(spacer)

        keycap = Gtk.Label(label="Esc")
        keycap.add_css_class("osd-keycap")
        header_box.append(keycap)

        main_box.append(header_box)

        # Văn bản nguồn (Mờ, tinh tế)
        src_preview = original.strip()
        if len(src_preview) > 160:
            src_preview = src_preview[:157] + "..."
        src_lbl = Gtk.Label(label=src_preview)
        src_lbl.add_css_class("osd-src")
        src_lbl.set_wrap(True)
        src_lbl.set_xalign(0.0)
        main_box.append(src_lbl)

        # Dải phân cách
        rule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rule.add_css_class("osd-rule")
        main_box.append(rule)

        # Văn bản dịch (Nổi bật, sắc nét, có cuộn nếu quá dài)
        dst_lbl = Gtk.Label(label=translated.strip())
        dst_lbl.add_css_class("osd-dst")
        dst_lbl.set_wrap(True)
        dst_lbl.set_xalign(0.0)
        dst_lbl.set_selectable(True)

        if len(translated) > 280 or "\n" in translated:
            scrolled = Gtk.ScrolledWindow()
            scrolled.add_css_class("osd-scroll")
            scrolled.set_max_content_height(380)
            scrolled.set_propagate_natural_height(True)
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_child(dst_lbl)
            main_box.append(scrolled)
        else:
            main_box.append(dst_lbl)

        # Footer & Hướng dẫn
        foot_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        foot_box.add_css_class("osd-foot")

        hint_lbl = Gtk.Label(label="Click để copy • Di chuột để giữ")
        hint_lbl.add_css_class("osd-hint")
        hint_lbl.set_xalign(0.0)
        foot_box.append(hint_lbl)
        main_box.append(foot_box)

        win.set_child(main_box)

        # 4. Quản lý tương tác: Hover, Click copy, Phím Esc, Bộ đếm tự đóng
        state = {
            "hovered": False,
            "remaining_ms": int(timeout_sec * 1000),
            "step_ms": 100
        }

        # Click để copy
        def on_click(gesture, n_press, x, y):
            if shutil.which("wl-copy"):
                try:
                    p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
                    p.communicate(input=translated.strip())
                except Exception:
                    pass
            hint_lbl.set_label("✓ Đã copy vào bộ nhớ đệm!")
            hint_lbl.remove_css_class("osd-hint")
            hint_lbl.add_css_class("osd-hint-copied")

        click_controller = Gtk.GestureClick.new()
        click_controller.connect("pressed", on_click)
        main_box.add_controller(click_controller)

        # Di chuột để tạm dừng đếm ngược
        def on_motion_enter(controller, x, y):
            state["hovered"] = True
            hint_lbl.set_label("Đang giữ hiển thị...")

        def on_motion_leave(controller):
            state["hovered"] = False
            hint_lbl.set_label("Click để copy • Di chuột để giữ")
            hint_lbl.remove_css_class("osd-hint-copied")
            hint_lbl.add_css_class("osd-hint")

        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("enter", on_motion_enter)
        motion_controller.connect("leave", on_motion_leave)
        main_box.add_controller(motion_controller)

        # Nhấn phím Esc để đóng
        def on_key_pressed(controller, keyval, keycode, modifier):
            if keyval == Gdk.KEY_Escape:
                win.close()
                app.quit()
                return True
            return False

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", on_key_pressed)
        win.add_controller(key_controller)

        # Đếm ngược tự ẩn
        def on_timer():
            if not state["hovered"]:
                state["remaining_ms"] -= state["step_ms"]
                if state["remaining_ms"] <= 0:
                    win.close()
                    app.quit()
                    return False
            return True

        GLIB_TIMER = GLib.timeout_add(state["step_ms"], on_timer)

        win.present()

    app.connect("activate", on_activate)
    app.run(None)

def show_osd(original: str, translated: str, src_lang: str = "auto",
             tgt_lang: str = "vi", engine: str = "Fast", timeout_sec: float = 6.0):
    """
    Khởi chạy floating OSD trong tiến trình nền độc lập.
    Không làm block CLI hay phím tắt.
    """
    env = os.environ.copy()
    layer_so = "/usr/lib64/libgtk4-layer-shell.so"
    if os.path.exists(layer_so):
        env["LD_PRELOAD"] = layer_so

    this_file = os.path.abspath(__file__)
    # Thêm project dir vào PYTHONPATH
    proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(this_file)))
    env["PYTHONPATH"] = proj_dir + ((":" + env["PYTHONPATH"]) if "PYTHONPATH" in env else "")

    cmd = [
        sys.executable,
        this_file,
        "--src", src_lang,
        "--tgt", tgt_lang,
        "--engine", engine,
        "--timeout", str(timeout_sec),
        "--orig", original,
        "--trans", translated
    ]

    try:
        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except Exception:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SuperTrans OSD Popup Card")
    parser.add_argument("--src", default="auto")
    parser.add_argument("--tgt", default="vi")
    parser.add_argument("--engine", default="Fast")
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--orig", required=True)
    parser.add_argument("--trans", required=True)
    args = parser.parse_args()

    run_osd_app(
        original=args.orig,
        translated=args.trans,
        src_lang=args.src,
        tgt_lang=args.tgt,
        engine=args.engine,
        timeout_sec=args.timeout
    )
