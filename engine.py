"""
Zalo Auto Messenger Engine
Cung cấp toàn bộ core xử lý tự động gửi tin nhắn Zalo Web,
kết nối Telegram Bot, quản lý Chrome và ghi log.
"""

import json
import os
import sys

# Đảm bảo mã hóa UTF-8 an toàn trên Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import random
import time
import glob
import subprocess
import io
import threading
import requests
import pyperclip
import win32clipboard
import win32con
import win32gui
import win32process
from PIL import Image
from datetime import datetime, timedelta

from selenium import webdriver
import selenium.webdriver.chrome.webdriver
import selenium.webdriver.chrome.service
import selenium.webdriver.chrome.options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

# ── Hàm lấy đường dẫn gốc (Tương thích cả .py và .exe) ──────────────────────
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "history.log")
ZALO_WEB_URL = "https://chat.zalo.me"
DEBUG_PORT = 9222
CHROME_PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profile")


def load_config():
    """Đọc file config.json từ thư mục gốc"""
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Không tìm thấy file config.json tại: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_data):
    """Lưu dữ liệu cấu hình vào config.json"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)


# ── Hệ thống Ghi Log đa kênh ──────────────────────────────────────────────
def write_log(msg, callback=None):
    """Ghi log ra console, file history.log và gửi tới UI callback nếu có"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    
    # In ra console an toàn, tuyệt đối không crash nếu console không hỗ trợ ký tự
    try:
        print(formatted_msg)
    except Exception:
        try:
            print(formatted_msg.encode('ascii', errors='backslashreplace').decode('ascii'))
        except Exception:
            pass

    # Ghi file với encoding utf-8
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except Exception:
        pass

    # Gửi tới UI callback
    if callback:
        try:
            callback(formatted_msg)
        except Exception:
            pass


# ── Tích hợp Telegram Bot ──────────────────────────────────────────────────
def get_telegram_updates_info(token):
    """
    Lấy danh sách người dùng hoặc nhóm đã tương tác với Bot gần đây từ getUpdates.
    Trả về (danh_sách_chat, error_message).
    """
    token = token.strip()
    if not token:
        return [], "Chưa nhập Bot Token!"
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        res = requests.get(url, timeout=10).json()
        if not res.get("ok"):
            return [], f"Lỗi Telegram API: {res.get('description')}"
        
        updates = res.get("result", [])
        chats = []
        seen_ids = set()
        for u in reversed(updates):
            msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member", {}).get("chat")
            if not msg:
                continue
            chat = msg.get("chat", {})
            from_user = msg.get("from", {})
            chat_id = chat.get("id") or from_user.get("id")
            if chat_id and chat_id not in seen_ids:
                seen_ids.add(chat_id)
                uname = chat.get("username") or from_user.get("username") or ""
                first_name = chat.get("first_name") or from_user.get("first_name") or chat.get("title") or "Unknown"
                chats.append({
                    "id": str(chat_id),
                    "username": uname,
                    "name": first_name,
                    "type": chat.get("type", "private")
                })
        return chats, None
    except Exception as e:
        return [], f"Lỗi kết nối Telegram: {e}"


def resolve_telegram_chat_id(token, chat_id_input, log_callback=None):
    """
    Nếu chat_id là số numeric, trả về trực tiếp.
    Nếu chat_id là @username hoặc tên, tra cứu qua getUpdates để tìm ID số.
    """
    token = token.strip()
    chat_id_input = str(chat_id_input).strip()
    if not token or not chat_id_input:
        return None, "Thiếu Token hoặc Chat ID"

    # Nếu đã là số nguyên (ID cá nhân hoặc ID nhóm dạng âm -100...)
    if chat_id_input.lstrip("-").isdigit():
        return chat_id_input, None

    # Nếu là dạng @username hoặc chuỗi
    clean_username = chat_id_input.lstrip("@").lower()
    chats, err = get_telegram_updates_info(token)
    if err:
        return None, err

    for c in chats:
        if c["username"].lower() == clean_username or str(c["id"]) == clean_username:
            return c["id"], None

    if chats:
        # Gợi ý danh sách chat đã thấy
        found_names = ", ".join([f"{c['name']} (ID: {c['id']})" for c in chats[:3]])
        return None, (
            f"Không tìm thấy @{clean_username} trong tin nhắn Bot. "
            f"Các tương tác gần nhất: {found_names}. Hãy mở Telegram và nhấn /start cho Bot!"
        )

    return None, (
        f"Chưa có tin nhắn nào từ @{clean_username} trong Bot. "
        "Hãy mở Telegram, tìm bot và nhấn /start, sau đó thử lại!"
    )


def send_telegram_notification(token, chat_id, message, log_callback=None):
    """Gửi thông báo tới Telegram"""
    if not token or not chat_id:
        return False, "Chưa cấu hình Telegram Token hoặc Chat ID"

    # Kiểm tra xem có cần resolve chat_id không
    resolved_id, err = resolve_telegram_chat_id(token, chat_id, log_callback)
    if err and not resolved_id:
        # Nếu không resolve được và người dùng nhập @channel công khai, thử gửi với chat_id gốc
        if str(chat_id).startswith("@"):
            target_id = chat_id
        else:
            return False, err
    else:
        target_id = resolved_id

    try:
        url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        payload = {
            "chat_id": target_id,
            "text": message,
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload, timeout=15).json()
        if res.get("ok"):
            return True, "Gửi thông báo Telegram thành công!"
        else:
            desc = res.get("description", "Không rõ lỗi")
            return False, f"Telegram API lỗi: {desc}"
    except Exception as e:
        return False, f"Lỗi kết nối Telegram: {e}"


# ── Xử lý Trình duyệt Chrome ───────────────────────────────────────────────
def find_chrome_path():
    """Tìm đường dẫn Chrome trên máy Windows"""
    possible_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def launch_chrome(log_callback=None):
    """Khởi động Chrome với remote debugging port và profile riêng, tối ưu chống White Screen trên VPS"""
    chrome_path = find_chrome_path()
    if not chrome_path:
        write_log("❌ Không tìm thấy Google Chrome trên máy tính!", log_callback)
        return False

    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    write_log(f"🚀 Khởi động Chrome (Port {DEBUG_PORT})...", log_callback)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        # Tắt thanh cảnh báo và thông báo rác
        "--test-type",
        "--disable-infobars",
        "--ignore-certificate-errors",
        "--disable-notifications",
        "--disable-popup-blocking",
        # Tối ưu chống White Screen & Freeze khi thu nhỏ trên VPS
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-dev-shm-usage",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-hang-monitor",
        "--disable-ipc-flooding-protection",
        "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling,HighEfficiencyModeAvailable,PageLifecycle,FreezingOnBatterySaver,Translate",
        ZALO_WEB_URL,
    ]

    try:
        subprocess.Popen(cmd)
        time.sleep(4)
        return True
    except Exception as e:
        write_log(f"❌ Không thể mở Chrome: {e}", log_callback)
        return False


def connect_chrome(log_callback=None, stop_event=None):
    """Kết nối Selenium tới Chrome đang chạy qua debugging port"""
    options = Options()
    options.debugger_address = f"127.0.0.1:{DEBUG_PORT}"

    # Thử kết nối lần 1
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        driver = None

    if driver is not None:
        write_log("✅ Đã kết nối thành công tới Chrome!", log_callback)
        return driver

    write_log("⚠ Chrome chưa mở port debug. Đang tự khởi động...", log_callback)

    # Tự mở Chrome
    if not launch_chrome(log_callback):
        return None

    # Thử kết nối lại
    for attempt in range(1, 4):
        if stop_event and stop_event.is_set():
            return None
        write_log(f"🔗 Đang kết nối lại Chrome ({attempt}/3)...", log_callback)
        driver = None
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            write_log(f"  (Thử lần {attempt} chưa thành công: {e})", log_callback)
            driver = None

        if driver is not None:
            write_log("✅ Đã kết nối thành công tới Chrome!", log_callback)
            return driver
        time.sleep(3)

    write_log("❌ Không thể kết nối tới Chrome sau 3 lần thử.", log_callback)
    return None


def check_zalo_login(driver, log_callback=None):
    """Kiểm tra xem đã đăng nhập Zalo Web thành công chưa"""
    try:
        # Tìm tab Zalo Web
        found_zalo = False
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "chat.zalo.me" in driver.current_url.lower():
                found_zalo = True
                break

        if not found_zalo:
            driver.get(ZALO_WEB_URL)
            time.sleep(3)

        inputs = driver.find_elements(By.CSS_SELECTOR, "input")
        if len(inputs) >= 1:
            return True
        return False
    except Exception:
        return False


def wait_for_login(driver, timeout=300, log_callback=None, stop_event=None):
    """Chờ người dùng quét mã QR đăng nhập"""
    write_log("📱 Vui lòng quét mã QR trên màn hình Chrome để đăng nhập Zalo...", log_callback)
    start_time = time.time()
    while time.time() - start_time < timeout:
        if stop_event and stop_event.is_set():
            return False
        if check_zalo_login(driver, log_callback):
            write_log("🎉 Đăng nhập Zalo Web thành công!", log_callback)
            return True
        time.sleep(3)
    write_log("❌ Hết thời gian chờ đăng nhập.", log_callback)
    return False


def ensure_page_ready(driver, log_callback=None, timeout=35):
    """
    Đảm bảo trang Zalo Web đã tải xong giao diện hoàn chỉnh.
    Tự động xử lý đánh thức DOM và phục hồi màn hình trắng (White Screen) khi Chrome bị ẩn Taskbar lâu trên VPS.
    """
    if isinstance(log_callback, (int, float)):
        timeout, log_callback = log_callback, None
    write_log("⏳ Đang kiểm tra trạng thái trang Zalo Web...", log_callback)
    
    # 1. Tìm hoặc chuyển tới tab Zalo Web
    found_zalo = False
    try:
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if "chat.zalo.me" in driver.current_url.lower():
                    found_zalo = True
                    break
            except Exception:
                continue
    except Exception:
        pass

    if not found_zalo:
        try:
            driver.get(ZALO_WEB_URL)
            time.sleep(5)
        except Exception:
            pass

    # 2. Đánh thức JS event loop và Visibility API của Zalo Web
    try:
        driver.execute_script("""
            window.dispatchEvent(new Event('focus'));
            document.dispatchEvent(new Event('visibilitychange'));
        """)
    except Exception:
        pass

    # 3. Đợi giao diện Zalo hiển thị đầy đủ
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            state = driver.execute_script("return document.readyState")
            if state == "complete":
                # Kiểm tra nếu trang bị rỗng / trắng (white screen)
                body_html = driver.execute_script("return document.body ? document.body.innerHTML : ''")
                if len(body_html) > 500:
                    search_input = find_search_input(driver)
                    if search_input and search_input.is_displayed():
                        time.sleep(1)
                        return True
        except Exception:
            pass
        time.sleep(2)

    # 4. Nếu sau timeout vẫn chưa thấy ô tìm kiếm hoặc trang trắng, tự động làm mới trang (Self-Healing)
    write_log("⚠ Phát hiện trang Zalo tải chậm hoặc bị đơ sau khi ẩn, đang làm mới trang (refresh)...", log_callback)
    try:
        driver.refresh()
        time.sleep(6)
        # Chờ sau khi refresh
        for _ in range(15):
            search_input = find_search_input(driver)
            if search_input and search_input.is_displayed():
                write_log("✅ Trang Zalo Web đã phục hồi thành công!", log_callback)
                return True
            time.sleep(1)
    except Exception as e:
        write_log(f"⚠ Lỗi khi làm mới trang: {e}", log_callback)

    return True


# ── Các thao tác gửi tin ───────────────────────────────────────────────────
def find_search_input(driver):
    """Tìm ô tìm kiếm bạn bè / nhóm"""
    selectors = [
        "#contact-search-input",
        "input#contact-search-input",
        "input[data-id='txt_Main_Search']",
        "input[placeholder*='Tìm kiếm']",
        "input[placeholder*='tìm kiếm']",
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
        "input[type='text']",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    return el
        except Exception:
            continue
    return None


def search_and_open_group(driver, group_name, delay=1.5, log_callback=None):
    """Tìm và mở nhóm chat"""
    write_log(f"  🔍 Tìm kiếm nhóm: {group_name}", log_callback)
    
    search_input = None
    for _ in range(5):
        search_input = find_search_input(driver)
        if search_input and search_input.is_displayed():
            break
        time.sleep(1)

    if not search_input:
        write_log("  ❌ Không tìm thấy ô tìm kiếm Zalo!", log_callback)
        return False

    try:
        # Nhấp chuột và focus an toàn (chống ElementClickInterceptedException khi có header che)
        try:
            driver.execute_script("arguments[0].focus();", search_input)
            search_input.click()
        except Exception:
            driver.execute_script("arguments[0].click();", search_input)
            driver.execute_script("arguments[0].focus();", search_input)
        time.sleep(0.4)

        # Xóa ô tìm kiếm
        try:
            search_input.send_keys(Keys.CONTROL + "a")
            time.sleep(0.2)
            search_input.send_keys(Keys.DELETE)
            time.sleep(0.2)
        except Exception:
            driver.execute_script("arguments[0].value = '';", search_input)

        pyperclip.copy(group_name)
        try:
            search_input.send_keys(Keys.CONTROL + "v")
        except Exception:
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
        time.sleep(delay * 2)

        try:
            search_input.send_keys(Keys.ENTER)
        except Exception:
            ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(delay)

        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass
        time.sleep(0.5)
        write_log(f"  ✅ Đã mở nhóm: {group_name}", log_callback)
        return True
    except Exception as e:
        write_log(f"  ❌ Lỗi khi tìm nhóm: {e}", log_callback)
        return False


def find_chat_input(driver):
    """Tìm ô soạn thảo tin nhắn (luôn tìm element mới nhất trong DOM)"""
    selectors = [
        "#richInput",
        "div[id='richInput']",
        "div.rich-input",
        "[contenteditable='true']",
    ]
    for sel in selectors:
        try:
            editables = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in editables:
                if el.is_displayed():
                    return el
        except Exception:
            continue
    return None


def paste_text_message(driver, message_file, delay=1.5, log_callback=None):
    """Paste nội dung văn bản từ file vào khung chat"""
    message_path = os.path.join(BASE_DIR, message_file)
    if not os.path.exists(message_path):
        write_log(f"  ⚠ Không tìm thấy file: {message_path}", log_callback)
        return False

    with open(message_path, "r", encoding="utf-8") as f:
        message = f.read().strip()

    if not message:
        write_log("  ⚠ Nội dung file tin nhắn rỗng, bỏ qua text.", log_callback)
        return False

    chat_input = find_chat_input(driver)
    if not chat_input:
        write_log("  ❌ Không tìm thấy khung soạn tin nhắn!", log_callback)
        return False

    try:
        try:
            chat_input.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", chat_input)
        time.sleep(0.3)

        pyperclip.copy(message)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
        time.sleep(delay)
        write_log("  ✅ Đã dán nội dung văn bản", log_callback)
        return True
    except Exception as e:
        write_log(f"  ❌ Lỗi khi dán tin nhắn: {e}", log_callback)
        return False


def copy_image_to_clipboard(image_path):
    """Copy file ảnh vào clipboard hệ điều hành dưới định dạng DIB"""
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


def paste_image(driver, images_folder, delay=1.5, log_callback=None):
    """Chọn ngẫu nhiên 1 ảnh từ thư mục và paste vào khung chat"""
    images_path = os.path.join(BASE_DIR, images_folder)
    if not os.path.exists(images_path):
        write_log(f"  ⚠ Không tìm thấy thư mục ảnh: {images_path}", log_callback)
        return False

    extensions = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp")
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(images_path, ext)))

    if not image_files:
        write_log("  ⚠ Không có ảnh nào trong thư mục images.", log_callback)
        return False

    img_path = random.choice(image_files)
    filename = os.path.basename(img_path)
    write_log(f"  🖼 Chọn ảnh ngẫu nhiên: {filename}", log_callback)

    try:
        copy_image_to_clipboard(img_path)
        time.sleep(0.5)

        chat_input = find_chat_input(driver)
        if chat_input:
            try:
                chat_input.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", chat_input)
            time.sleep(0.3)

        ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
        time.sleep(delay * 2)
        write_log(f"  ✅ Đã dán ảnh: {filename}", log_callback)
        return True
    except Exception as e:
        write_log(f"  ❌ Lỗi khi dán ảnh: {e}", log_callback)
        return False


def dismiss_link_preview(driver, log_callback=None):
    """Tự động đóng thẻ xem trước liên kết (chỉ nhắm đúng khung link preview trong chat)"""
    selectors = [
        "#linkPreview .preview-close",
        ".chat-input-link-preview .preview-close",
        "#linkPreview i.preview-close",
        "#linkPreview [class*='close']",
    ]
    for sel in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                if el.is_displayed():
                    el.click()
                    time.sleep(0.4)
                    write_log("  ✕ Đã tắt thẻ xem trước liên kết (Link Preview)", log_callback)
                    return True
        except Exception:
            continue
    return False


def send_message(driver, log_callback=None):
    """Bấm Enter để gửi tin nhắn (thử gửi trực tiếp qua chat input hoặc ActionChains)"""
    try:
        chat_input = find_chat_input(driver)
        if chat_input:
            try:
                chat_input.send_keys(Keys.ENTER)
                time.sleep(1.5)
                write_log("  🚀 Đã bấm gửi tin nhắn!", log_callback)
                return True
            except Exception:
                pass

        # Fallback gửi phím Enter
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(1.5)
        write_log("  🚀 Đã bấm gửi tin nhắn!", log_callback)
        return True
    except Exception as e:
        write_log(f"  ❌ Lỗi gửi tin: {e}", log_callback)
        return False


def kill_all_background_processes(log_callback=None):
    """Tắt toàn bộ tiến trình Chrome và ChromeDriver chạy ngầm để giải phóng RAM/CPU"""
    write_log("🛑 Đang đóng toàn bộ tiến trình chạy ngầm (Chrome, ChromeDriver)...", log_callback)
    killed = []
    
    # 1. Đóng chromedriver
    try:
        res = subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], capture_output=True, text=True)
        if res.returncode == 0:
            killed.append("chromedriver.exe")
    except Exception:
        pass

    # 2. Đóng chrome
    try:
        res = subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True, text=True)
        if res.returncode == 0:
            killed.append("chrome.exe")
    except Exception:
        pass

    if killed:
        write_log(f"✅ Đã dọn dẹp thành công các tiến trình: {', '.join(killed)}", log_callback)
    else:
        write_log("ℹ Không có tiến trình Chrome/ChromeDriver ngầm nào cần tắt.", log_callback)
    return True


def restore_chrome_window(driver=None, log_callback=None):
    """Bung cửa sổ Chrome lên toàn màn hình (Maximize / Restore) khi bắt đầu gửi tin"""
    success = False
    if driver is not None:
        try:
            driver.maximize_window()
            success = True
        except Exception:
            pass

    try:
        def enum_windows_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if "Chrome" in class_name or "Zalo" in title or "Google Chrome" in title:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        success = True
    except Exception:
        pass

    if success and log_callback:
        write_log("🪟 Đã hiển thị cửa sổ Chrome toàn màn hình để thực hiện gửi tin.", log_callback)
    return success


def minimize_chrome_window(driver=None, log_callback=None):
    """Thu nhỏ cửa sổ Chrome xuống thanh Taskbar"""
    success = False
    # 1. Thử dùng Selenium minimize_window
    if driver is not None:
        try:
            driver.minimize_window()
            success = True
        except Exception:
            pass

    # 2. Dùng Windows API (win32gui) để chắc chắn thu nhỏ tất cả cửa sổ Chrome liên quan
    try:
        def enum_windows_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if "Chrome" in class_name or "Zalo" in title or "Google Chrome" in title:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWMINIMIZED)
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        success = True
    except Exception:
        pass

    if success and log_callback:
        write_log("🪟 Đã thu nhỏ cửa sổ Chrome xuống thanh Taskbar trong thời gian nghỉ.", log_callback)
    return success


# ── Worker Điều phối Tiến trình Gửi Tin ────────────────────────────────────
class ZaloAutoWorker:
    def __init__(self, log_callback=None, status_callback=None):
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.stop_event = threading.Event()
        self.thread = None
        self.driver = None

    def log(self, msg):
        write_log(msg, self.log_callback)

    def set_status(self, status):
        if self.status_callback:
            try:
                self.status_callback(status)
            except Exception:
                pass

    def force_kill(self):
        """Dừng khẩn cấp và dọn dẹp toàn bộ tiến trình ngầm"""
        self.stop_event.set()
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        kill_all_background_processes(self.log_callback)
        self.set_status("SẴN SÀNG")

    def start(self):
        if self.thread and self.thread.is_alive():
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()
        self.log("🛑 Đang gửi tín hiệu dừng tiến trình...")
        self.set_status("Đang dừng...")

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def _sleep_interruptible(self, seconds):
        """Ngủ nhưng có thể bị ngắt ngay lập tức khi người dùng bấm Stop"""
        step = 0.5
        waited = 0.0
        while waited < seconds:
            if self.stop_event.is_set():
                return False
            time.sleep(step)
            waited += step
        return True

    def _is_group_in_sleep_hours(self, group_name, config):
        """Kiểm tra xem nhóm có nằm trong khung giờ nghỉ cấu hình không"""
        if not config.get("sleep_hours_enabled", True):
            return False

        current_hour = datetime.now().hour
        start_hour = config.get("sleep_hours_start", 0)
        end_hour = config.get("sleep_hours_end", 6)
        sleep_groups = [g.lower().strip() for g in config.get("sleep_hours_groups", [])]

        # Kiểm tra điều kiện giờ (hỗ trợ cả trường hợp vắt qua đêm ví dụ từ 22h đến 6h)
        in_time_range = False
        if start_hour < end_hour:
            in_time_range = (start_hour <= current_hour < end_hour)
        else:
            in_time_range = (current_hour >= start_hour or current_hour < end_hour)

        if in_time_range:
            # Nếu danh sách nhóm rỗng -> áp dụng cho tất cả
            if not sleep_groups:
                return True
            # Nếu có danh sách chỉ định
            if group_name.lower().strip() in sleep_groups:
                return True

        return False

    def _send_round(self, config):
        groups = config.get("groups", [])
        message_file = config.get("message_file", "message.txt")
        images_folder = config.get("images_folder", "images")
        delay = config.get("delay_between_actions", 1.5)
        delay_min = config.get("delay_between_groups_min", 30)
        delay_max = config.get("delay_between_groups_max", 60)

        # 1. Luôn hiển thị Chrome toàn màn hình khi bắt đầu gửi
        restore_chrome_window(self.driver, self.log_callback)

        self.log("=" * 55)
        self.log(f"🚀 BẮT ĐẦU VÒNG GỬI TIN: {len(groups)} nhóm")
        self.log("=" * 55)

        if not ensure_page_ready(self.driver, self.log_callback):
            self.log("❌ Trang Zalo Web không phản hồi, thử tải lại...")
            return False

        success_groups = []
        fail_groups = []
        skipped_groups = []

        for idx, group_name in enumerate(groups, 1):
            if self.stop_event.is_set():
                self.log("⏹ Đã nhận lệnh Dừng từ người dùng.")
                break

            self.log(f"\n──────────────────────────────────────────────────")
            self.log(f"📌 [{idx}/{len(groups)}] Xử lý nhóm: {group_name}")
            self.log(f"──────────────────────────────────────────────────")

            # Kiểm tra giờ nghỉ
            if self._is_group_in_sleep_hours(group_name, config):
                self.log(f"  ⏸ Nhóm '{group_name}' đang trong khung giờ nghỉ. Bỏ qua.")
                skipped_groups.append(group_name)
                continue

            try:
                # 1. Tìm & mở nhóm
                if not search_and_open_group(self.driver, group_name, delay, self.log_callback):
                    fail_groups.append(group_name)
                    continue

                if self.stop_event.is_set():
                    break

                # 2. Dán hình ảnh trước (để tạo tin nhắn media kèm caption)
                image_ok = paste_image(self.driver, images_folder, delay, self.log_callback)

                if self.stop_event.is_set():
                    break

                # 3. Dán nội dung văn bản sau (văn bản sẽ trở thành Caption đính liền vào ảnh)
                text_ok = paste_text_message(self.driver, message_file, delay, self.log_callback)

                # 4. Tắt thẻ xem trước link nếu xuất hiện (tránh tách tin nhắn)
                dismiss_link_preview(self.driver, self.log_callback)

                if not text_ok and not image_ok:
                    self.log(f"  ❌ Không có nội dung để gửi cho nhóm: {group_name}")
                    fail_groups.append(group_name)
                    continue

                if self.stop_event.is_set():
                    break

                # 5. Bấm gửi (Cả ảnh và text được gửi cùng nhau trong 1 tin nhắn)
                if send_message(self.driver, self.log_callback):
                    success_groups.append(group_name)
                    self.log(f"  🎉 Thành công: {group_name}")
                else:
                    fail_groups.append(group_name)
                    self.log(f"  ❌ Gửi thất bại: {group_name}")

            except Exception as e:
                fail_groups.append(group_name)
                self.log(f"  ❌ Ngoại lệ tại nhóm {group_name}: {e}")

            # Nghỉ ngẫu nhiên trước nhóm kế tiếp
            if idx < len(groups) and not self.stop_event.is_set():
                wait_sec = random.randint(delay_min, delay_max)
                self.log(f"  ⏳ Chờ ngẫu nhiên {wait_sec}s trước khi sang nhóm kế tiếp...")
                if not self._sleep_interruptible(wait_sec):
                    break

        # Kết thúc vòng
        total = len(groups)
        ok_cnt = len(success_groups)
        fail_cnt = len(fail_groups)
        skip_cnt = len(skipped_groups)

        self.log(f"\n=======================================================")
        self.log(f"📊 TỔNG KẾT VÒNG GỬI:")
        self.log(f"   • Thành công: {ok_cnt}/{total}")
        self.log(f"   • Thất bại:   {fail_cnt}/{total}")
        if skip_cnt > 0:
            self.log(f"   • Bỏ qua (giờ nghỉ): {skip_cnt}")
        self.log(f"=======================================================")

        # Báo cáo qua Telegram nếu được bật
        if config.get("telegram_enabled", False):
            token = config.get("telegram_bot_token", "")
            chat_id = config.get("telegram_chat_id", "")
            if token and chat_id:
                time_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
                report_msg = (
                    f"🤖 <b>BÁO CÁO ZALO AUTO MESSENGER</b>\n"
                    f"⏱ Thời gian: <code>{time_str}</code>\n"
                    f"────────────────────\n"
                    f"✅ <b>Thành công:</b> {ok_cnt}/{total} nhóm\n"
                    f"❌ <b>Thất bại:</b> {fail_cnt} nhóm\n"
                )
                if fail_groups:
                    report_msg += f"⚠️ <i>Nhóm lỗi: {', '.join(fail_groups)}</i>\n"
                if skip_cnt > 0:
                    report_msg += f"⏸ <i>Tạm hoãn (giờ nghỉ): {skip_cnt} nhóm</i>\n"

                report_msg += f"💤 <i>Đang chờ vòng lặp tiếp theo...</i>"

                self.log("✈ Đang gửi báo cáo tổng kết qua Telegram...")
                ok, t_msg = send_telegram_notification(token, chat_id, report_msg, self.log_callback)
                if ok:
                    self.log("✅ Đã gửi báo cáo Telegram thành công!")
                else:
                    self.log(f"⚠ Báo cáo Telegram thất bại: {t_msg}")

        # Tự động thu nhỏ Chrome xuống Taskbar sau khi gửi xong tất cả các nhóm trong vòng
        if config.get("minimize_chrome", True) and not self.stop_event.is_set():
            minimize_chrome_window(self.driver, self.log_callback)

        return True

    def _run(self):
        self.set_status("Đang khởi động...")
        self.log("╔══════════════════════════════════════════════════════════╗")
        self.log("║       ZALO AUTO MESSENGER PRO - BẮT ĐẦU CHẠY             ║")
        self.log("╚══════════════════════════════════════════════════════════╝")

        try:
            config = load_config()
        except Exception as e:
            self.log(f"❌ Lỗi tải cấu hình config.json: {e}")
            self.set_status("Lỗi cấu hình")
            return

        # Kết nối Chrome
        self.set_status("Đang kết nối Chrome...")
        self.driver = connect_chrome(self.log_callback, self.stop_event)
        if not self.driver:
            self.set_status("Không thể kết nối Chrome")
            return

        if self.stop_event.is_set():
            self.set_status("Đã dừng")
            return

        # Kiểm tra đăng nhập
        if not check_zalo_login(self.driver, self.log_callback):
            self.set_status("Chờ quét mã QR...")
            if not wait_for_login(self.driver, 300, self.log_callback, self.stop_event):
                self.set_status("Chưa đăng nhập")
                return

        # Vòng lặp chính
        while not self.stop_event.is_set():
            # Reload config mỗi vòng
            try:
                config = load_config()
            except Exception:
                pass

            try:
                self.set_status("Đang gửi tin...")
                self._send_round(config)
            except Exception as e:
                import traceback
                self.log(f"❌ Lỗi ngoài ý muốn trong vòng gửi: {e}\n{traceback.format_exc()}")

            if self.stop_event.is_set():
                break

            interval_hours = config.get("interval_hours", 2)
            next_time = datetime.now() + timedelta(hours=interval_hours)
            self.log(f"\n⏰ Vòng gửi kế tiếp dự kiến lúc: {next_time.strftime('%H:%M:%S %d/%m/%Y')}")
            self.log(f"💤 Tạm nghỉ {interval_hours} giờ...\n")

            self.set_status(f"Nghỉ tới {next_time.strftime('%H:%M')}")
            # Ngủ ngắt quãng
            if not self._sleep_interruptible(interval_hours * 3600):
                break

        self.set_status("Đã dừng")
        self.log("⏹ Đã dừng tiến trình Auto Zalo.")
