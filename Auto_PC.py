"""
Zalo PC Auto Messenger
Tự động gửi tin nhắn văn bản + hình ảnh đến các nhóm Zalo PC (Desktop).
Yêu cầu: Zalo PC phải đang mở và đăng nhập sẵn.
"""

import json
import os
import sys
import random
import time
import glob
import ctypes
import io
import struct
import pyautogui
import pyperclip
import win32clipboard
import win32con
import win32gui
from PIL import Image
from datetime import datetime, timedelta

# ── Cấu hình ───────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    """Đọc file config.json"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log(msg):
    """In log có kèm timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


# ── Clipboard helpers ──────────────────────────────────────────────────────

def copy_text_to_clipboard(text):
    """Copy văn bản vào clipboard"""
    pyperclip.copy(text)


def copy_image_to_clipboard(image_path):
    """Copy hình ảnh vào clipboard dưới dạng BMP (Windows clipboard)"""
    img = Image.open(image_path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    output = io.BytesIO()
    img.save(output, format="BMP")
    bmp_data = output.getvalue()
    bmp_without_header = bmp_data[14:]

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, bmp_without_header)
    finally:
        win32clipboard.CloseClipboard()


# ── Zalo Window helpers ───────────────────────────────────────────────────

def find_zalo_window(title_keyword="Zalo"):
    """Tìm cửa sổ Zalo PC"""
    result = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if title_keyword.lower() in window_title.lower():
                result.append(hwnd)

    win32gui.EnumWindows(enum_handler, None)
    return result[0] if result else None


def activate_zalo_window(hwnd):
    """Đưa cửa sổ Zalo lên trước"""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
    except Exception as e:
        log(f"  ⚠ Không thể kích hoạt cửa sổ Zalo: {e}")
        try:
            pyautogui.press("alt")
            time.sleep(0.1)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.5)
        except Exception:
            pass


# ── Thao tác chính ────────────────────────────────────────────────────────

def search_and_open_group(group_name, delay):
    """Tìm kiếm và mở nhóm Zalo bằng ô tìm kiếm"""
    log(f"  🔍 Tìm kiếm nhóm: {group_name}")

    pyautogui.hotkey("ctrl", "f")
    time.sleep(delay)

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)

    copy_text_to_clipboard(group_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(delay * 1.5)

    pyautogui.press("enter")
    time.sleep(delay)

    pyautogui.press("escape")
    time.sleep(0.5)

    log(f"  ✅ Đã mở nhóm: {group_name}")


def paste_text_message(message_file, delay):
    """Đọc và paste tin nhắn văn bản vào chat"""
    message_path = os.path.join(SCRIPT_DIR, message_file)
    if not os.path.exists(message_path):
        log(f"  ⚠ Không tìm thấy file tin nhắn: {message_path}")
        return False

    with open(message_path, "r", encoding="utf-8") as f:
        message = f.read().strip()

    if not message:
        log("  ⚠ File tin nhắn rỗng, bỏ qua.")
        return False

    log(f"  📝 Đang paste tin nhắn ({len(message)} ký tự)...")

    copy_text_to_clipboard(message)
    time.sleep(0.3)

    window_rect = pyautogui.getWindowsWithTitle("Zalo")
    if window_rect:
        w = window_rect[0]
        chat_x = w.left + w.width // 2
        chat_y = w.top + w.height - 100
        pyautogui.click(chat_x, chat_y)
        time.sleep(0.3)

    pyautogui.hotkey("ctrl", "v")
    time.sleep(delay)

    log("  ✅ Đã paste tin nhắn văn bản")
    return True


def paste_images(images_folder, delay):
    """Chọn ngẫu nhiên 1 hình ảnh từ thư mục và paste vào chat"""
    images_path = os.path.join(SCRIPT_DIR, images_folder)
    if not os.path.exists(images_path):
        log(f"  ⚠ Không tìm thấy thư mục hình ảnh: {images_path}")
        return False

    image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp")
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(images_path, ext)))

    if not image_files:
        log("  ⚠ Không có hình ảnh nào trong thư mục, bỏ qua.")
        return False

    img_path = random.choice(image_files)
    filename = os.path.basename(img_path)
    log(f"  🖼 Chọn ngẫu nhiên 1/{len(image_files)} ảnh: {filename}")

    copy_image_to_clipboard(img_path)
    time.sleep(0.3)

    pyautogui.hotkey("ctrl", "v")
    time.sleep(delay)

    log(f"  ✅ Đã paste ảnh: {filename}")
    return True


def send_message():
    """Nhấn Enter để gửi tin nhắn"""
    log("  📤 Đang gửi tin nhắn...")
    pyautogui.press("enter")
    time.sleep(1)
    log("  ✅ Đã gửi tin nhắn!")


# ── Quy trình chính ──────────────────────────────────────────────────────

def send_to_all_groups(config):
    """Gửi tin nhắn đến tất cả các nhóm"""
    groups = config["groups"]
    message_file = config["message_file"]
    images_folder = config["images_folder"]
    delay = config.get("delay_between_actions", 1.5)
    group_delay = config.get("delay_between_groups", 3.0)
    zalo_title = config.get("zalo_window_title", "Zalo")

    log("=" * 60)
    log(f"🚀 Bắt đầu gửi tin nhắn đến {len(groups)} nhóm")
    log("=" * 60)

    hwnd = find_zalo_window(zalo_title)
    if not hwnd:
        log("❌ Không tìm thấy cửa sổ Zalo PC! Hãy chắc chắn Zalo đang mở.")
        return False

    activate_zalo_window(hwnd)
    log("✅ Đã kích hoạt cửa sổ Zalo")
    time.sleep(1)

    success_count = 0
    fail_count = 0

    for idx, group_name in enumerate(groups, 1):
        log(f"\n{'─' * 50}")
        log(f"📌 Nhóm [{idx}/{len(groups)}]: {group_name}")
        log(f"{'─' * 50}")

        try:
            search_and_open_group(group_name, delay)
            paste_text_message(message_file, delay)
            paste_images(images_folder, delay)
            send_message()

            success_count += 1
            log(f"  🎉 Hoàn thành gửi tin cho nhóm: {group_name}")

        except Exception as e:
            fail_count += 1
            log(f"  ❌ Lỗi khi gửi tin cho nhóm {group_name}: {e}")

        if idx < len(groups):
            log(f"\n  ⏳ Chờ {group_delay}s trước khi chuyển nhóm tiếp theo...")
            time.sleep(group_delay)

    log(f"\n{'=' * 60}")
    log(f"📊 Kết quả: Thành công {success_count}/{len(groups)}, Thất bại: {fail_count}")
    log(f"{'=' * 60}")
    return True


def run_scheduler(config):
    """Chạy lặp lại mỗi N giờ"""
    interval_hours = config.get("interval_hours", 3)

    log("╔══════════════════════════════════════════════════════════╗")
    log("║          ZALO PC AUTO MESSENGER - Đang chạy...          ║")
    log("╚══════════════════════════════════════════════════════════╝")
    log(f"📋 Nhóm: {', '.join(config['groups'])}")
    log(f"⏰ Lặp lại mỗi: {interval_hours} giờ")
    log(f"📝 File tin nhắn: {config['message_file']}")
    log(f"🖼 Thư mục ảnh: {config['images_folder']}")
    log("")

    log("▶ Gửi lần đầu tiên ngay bây giờ...")
    send_to_all_groups(config)

    while True:
        next_run = datetime.now() + timedelta(hours=interval_hours)
        log(f"\n⏰ Lần gửi tiếp theo: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"💤 Đang chờ {interval_hours} giờ... (Nhấn Ctrl+C để dừng)\n")

        try:
            time.sleep(interval_hours * 3600)
        except KeyboardInterrupt:
            log("\n🛑 Đã dừng bởi người dùng (Ctrl+C)")
            sys.exit(0)

        try:
            config = load_config()
            log("🔄 Đã tải lại cấu hình từ config.json")
        except Exception as e:
            log(f"⚠ Không thể tải lại config, dùng config cũ: {e}")

        send_to_all_groups(config)


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.3

    try:
        config = load_config()
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file config.json tại: {CONFIG_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi đọc config.json: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ZALO PC AUTO MESSENGER")
    print("=" * 60)
    print(f"  Nhóm sẽ gửi ({len(config['groups'])}):")
    for g in config["groups"]:
        print(f"    • {g}")
    print(f"  Lặp lại mỗi: {config.get('interval_hours', 3)} giờ")
    print(f"  File tin nhắn: {config['message_file']}")
    print(f"  Thư mục ảnh: {config['images_folder']}")
    print("=" * 60)
    print("\n⚠ Lưu ý:")
    print("  - Zalo PC phải đang mở và đăng nhập")
    print("  - Không dùng chuột/bàn phím khi script đang gửi")
    print("  - Di chuột vào góc TRÊN-TRÁI màn hình để dừng khẩn cấp")
    print("")

    confirm = input("▶ Nhấn Enter để bắt đầu (hoặc Ctrl+C để hủy)... ")

    run_scheduler(config)
