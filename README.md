# Zalo Workflow Automation & Messaging Tool 🤖

> **Ứng dụng Desktop tự động hóa quy trình gửi tin nhắn, chăm sóc khách hàng và thông báo định kỳ trên nền tảng Zalo với giao diện GUI hiện đại, tối ưu cho Windows VPS.**

---

## 🌟 Tính Năng Nổi Bật

- 🖥️ **Giao diện Modern Desktop GUI:** Xây dựng bằng `CustomTkinter` mang lại trải nghiệm tối giản, trực quan, hỗ trợ Dark Mode và tiêu tốn cực ít tài nguyên RAM (~40MB).
- 🔄 **Duy trì phiên làm việc (Session Persistence):** Tận dụng Profile trình duyệt riêng biệt (`chrome_profile`), duy trì cookie đăng nhập dài hạn, loại bỏ nguy cơ bị đăng xuất hoặc checkpoint bảo mật.
- ⏱️ **Kiểm soát nhịp độ & Rate Limiting:** 
  - Điều tiết độ trễ ngẫu nhiên giữa các thao tác (Random Jitter).
  - Giãn cách thời gian gửi giữa các nhóm khách hàng theo khoảng cấu hình (`delay_between_groups_min` / `max`).
  - Hỗ trợ thiết lập khung giờ nghỉ ngơi (`sleep_hours`).
- 🔔 **Cảnh báo tiến trình qua Telegram:** Tự động gửi thông báo báo cáo tiến độ và trạng thái chiến dịch đến quản trị viên qua Telegram Bot.
- 📦 **Đóng gói Binary (.EXE):** Hỗ trợ biên dịch thành tệp thực thi Windows độc lập thông qua `PyInstaller`.

---

## 🛠️ Tech Stack

- **Ngôn ngữ:** Python 3.10+
- **Giao diện:** CustomTkinter, Tkinter
- **Trình duyệt & Tự động hóa:** Chrome DevTools Protocol / Selenium / Web Automation
- **Mạng & Thông báo:** Requests, Telegram Bot API
- **Đóng gói:** PyInstaller

---

## 📁 Cấu Trúc Dự Án

```
├── images/               # Thư mục chứa hình ảnh đính kèm tin nhắn
├── app.py                # Giao diện đồ họa người dùng (CustomTkinter GUI)
├── engine.py             # Động cơ tự động hóa lõi (Logic gửi tin, rate limit)
├── Auto.py               # Script thực thi tác vụ nền
├── Auto_PC.py            # Tác vụ tự động hóa nâng cao cho máy tính/VPS
├── config.example.json   # Tệp mẫu cấu hình độ trễ, nhóm và bot token
├── message.example.txt   # Tệp mẫu kịch bản tin nhắn gửi đi
├── start_chrome.bat      # Script khởi tạo Chrome với Debugging Port & Profile riêng
├── build.bat             # Script tự động hóa đóng gói ứng dụng với PyInstaller
└── ZaloAuto.spec         # Cấu hình biên dịch PyInstaller
```

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Cài đặt môi trường
```bash
git clone https://github.com/<your-username>/zalo-workflow-automation.git
cd zalo-workflow-automation
pip install customtkinter requests
```

### 2. Thiết lập cấu hình
Sao chép các file mẫu:
```bash
cp config.example.json config.json
cp message.example.txt message.txt
```
Chỉnh sửa `config.json` để điền danh sách nhóm cần gửi, cấu hình độ trễ và token thông báo Telegram.

### 3. Khởi chạy
```bash
python app.py
```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)
Dự án được xây dựng phục vụ cho mục đích học tập, nghiên cứu kỹ thuật tự động hóa phần mềm (Software Automation) và quản lý thông báo nội bộ. Người sử dụng cần tuân thủ các điều khoản dịch vụ của nền tảng và quy định pháp luật liên quan.
