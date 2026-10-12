"""
Zalo Auto Messenger GUI
Giao diện điều khiển đồ họa hiện đại, tối giản, trực quan và nhẹ nhàng cho VPS.
Sử dụng CustomTkinter.
"""

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

import json
import threading
import queue
import subprocess
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox

import engine

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ZaloAutoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Zalo Auto Messenger Pro v2.0")
        self.geometry("1020x680")
        self.minsize(880, 600)

        # Queue để thread an toàn giao tiếp với GUI
        self.log_queue = queue.Queue()

        # Engine Worker
        self.worker = engine.ZaloAutoWorker(
            log_callback=self.enqueue_log,
            status_callback=self.update_status_badge
        )

        # Tạo giao diện
        self._create_widgets()

        # Tải cấu hình vào form
        self._load_config_into_ui()

        # Bắt đầu vòng lặp xử lý log queue
        self.after(100, self._process_log_queue)

        # Bắt sự kiện tắt cửa sổ
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        # Grid 2 cột: Cột trái (Cấu hình & Điều khiển), Cột phải (Terminal Log)
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ══════════════════════════════════════════════════════════
        # CỘT TRÁI: ĐIỀU KHIỂN & CẤU HÌNH
        # ══════════════════════════════════════════════════════════
        left_frame = ctk.CTkFrame(self, corner_radius=10)
        left_frame.grid(row=0, column=0, padx=(15, 8), pady=15, sticky="nsew")
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # 1. Header & Status
        header_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        lbl_title = ctk.CTkLabel(
            header_frame,
            text="ZALO AUTO PRO",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_title.pack(side="left")

        self.badge_status = ctk.CTkLabel(
            header_frame,
            text="SẴN SÀNG",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155",
            text_color="#38bdf8",
            corner_radius=12,
            width=110,
            height=26
        )
        self.badge_status.pack(side="right")

        # 2. Thanh nút hành động chính (Start / Stop / Kill)
        action_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        action_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)

        self.btn_start = ctk.CTkButton(
            action_frame,
            text="▶ BẮT ĐẦU",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=40,
            command=self._on_start
        )
        self.btn_start.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            action_frame,
            text="⏹ DỪNG LẠI",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            height=40,
            state="disabled",
            command=self._on_stop
        )
        self.btn_stop.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.btn_kill_all = ctk.CTkButton(
            action_frame,
            text="⚡ TẮT TOÀN BỘ TIẾN TRÌNH NGẦM (CHROME/DRIVER)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            height=32,
            command=self._on_kill_all
        )
        self.btn_kill_all.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="ew")

        # 3. Tab Cấu hình dạng cuộn (Scrollable Frame)
        scroll_config = ctk.CTkScrollableFrame(left_frame, label_text="THIẾT LẬP CẤU HÌNH")
        scroll_config.grid(row=2, column=0, padx=15, pady=5, sticky="nsew")
        scroll_config.grid_columnconfigure(0, weight=1)

        # ── Group 1: Lịch trình gửi ──
        sec_schedule = ctk.CTkFrame(scroll_config, fg_color="#1e293b", corner_radius=8)
        sec_schedule.pack(fill="x", pady=6, padx=4)

        ctk.CTkLabel(sec_schedule, text="⏱ Lịch trình & Giãn cách", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        # Lặp lại
        row_interval = ctk.CTkFrame(sec_schedule, fg_color="transparent")
        row_interval.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_interval, text="Lặp lại mỗi vòng (giờ):").pack(side="left")
        self.entry_interval = ctk.CTkEntry(row_interval, width=70)
        self.entry_interval.pack(side="right")

        # Delay ngẫu nhiên giữa các nhóm
        row_delay = ctk.CTkFrame(sec_schedule, fg_color="transparent")
        row_delay.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_delay, text="Nghỉ giữa 2 nhóm (giây):").pack(side="left")
        self.entry_delay_max = ctk.CTkEntry(row_delay, width=45)
        self.entry_delay_max.pack(side="right")
        ctk.CTkLabel(row_delay, text=" - ").pack(side="right", padx=2)
        self.entry_delay_min = ctk.CTkEntry(row_delay, width=45)
        self.entry_delay_min.pack(side="right")

        # Tùy chọn thu nhỏ Chrome
        self.switch_minimize = ctk.CTkSwitch(sec_schedule, text="🪟 Thu nhỏ Chrome xuống Taskbar khi chạy", font=ctk.CTkFont(size=12, weight="bold"))
        self.switch_minimize.pack(anchor="w", padx=10, pady=(4, 8))

        # ── Group 2: Khung giờ nghỉ đêm ──
        sec_sleep = ctk.CTkFrame(scroll_config, fg_color="#1e293b", corner_radius=8)
        sec_sleep.pack(fill="x", pady=6, padx=4)

        self.switch_sleep = ctk.CTkSwitch(sec_sleep, text="🌙 Bật khung giờ nghỉ đêm", font=ctk.CTkFont(size=13, weight="bold"))
        self.switch_sleep.pack(anchor="w", padx=10, pady=(8, 4))

        row_sleep_time = ctk.CTkFrame(sec_sleep, fg_color="transparent")
        row_sleep_time.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_sleep_time, text="Khung giờ (từ ...h đến ...h):").pack(side="left")
        self.entry_sleep_end = ctk.CTkEntry(row_sleep_time, width=45)
        self.entry_sleep_end.pack(side="right")
        ctk.CTkLabel(row_sleep_time, text=" -> ").pack(side="right", padx=2)
        self.entry_sleep_start = ctk.CTkEntry(row_sleep_time, width=45)
        self.entry_sleep_start.pack(side="right")

        ctk.CTkLabel(sec_sleep, text="Nhóm áp dụng giờ nghỉ (cách nhau dấu phẩy, để trống = tất cả):", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=10, pady=(4, 2))
        self.entry_sleep_groups = ctk.CTkEntry(sec_sleep, placeholder_text="Ví dụ: box super3 chú bé rồng online")
        self.entry_sleep_groups.pack(fill="x", padx=10, pady=(0, 8))

        # ── Group 3: Báo cáo Telegram ──
        sec_tele = ctk.CTkFrame(scroll_config, fg_color="#1e293b", corner_radius=8)
        sec_tele.pack(fill="x", pady=6, padx=4)

        self.switch_tele = ctk.CTkSwitch(sec_tele, text="✈ Báo cáo qua Telegram Bot", font=ctk.CTkFont(size=13, weight="bold"))
        self.switch_tele.pack(anchor="w", padx=10, pady=(8, 4))

        ctk.CTkLabel(sec_tele, text="Bot Token:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(2, 0))
        self.entry_tele_token = ctk.CTkEntry(sec_tele, placeholder_text="Nhập bot token...")
        self.entry_tele_token.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(sec_tele, text="Chat ID hoặc Username (Ví dụ: @DuncanNro hoặc ID số):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(2, 0))
        
        tele_id_row = ctk.CTkFrame(sec_tele, fg_color="transparent")
        tele_id_row.pack(fill="x", padx=10, pady=(0, 6))
        
        self.entry_tele_chat_id = ctk.CTkEntry(tele_id_row, placeholder_text="Ví dụ: 6123456789 hoặc @DuncanNro")
        self.entry_tele_chat_id.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_get_tele_id = ctk.CTkButton(
            tele_id_row,
            text="🔍 Lấy ID",
            width=70,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._on_get_telegram_chat_id
        )
        self.btn_get_tele_id.pack(side="right")

        self.btn_test_tele = ctk.CTkButton(
            sec_tele,
            text="✈ Gửi Thử Thông Báo Telegram",
            font=ctk.CTkFont(size=12),
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=30,
            command=self._on_test_telegram
        )
        self.btn_test_tele.pack(fill="x", padx=10, pady=(0, 8))

        # ── Group 4: Danh sách nhóm ──
        sec_groups = ctk.CTkFrame(scroll_config, fg_color="#1e293b", corner_radius=8)
        sec_groups.pack(fill="x", pady=6, padx=4)

        ctk.CTkLabel(sec_groups, text="📋 Danh sách tên nhóm (Mỗi nhóm 1 dòng):", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.txt_groups = ctk.CTkTextbox(sec_groups, height=130)
        self.txt_groups.pack(fill="x", padx=10, pady=(0, 8))

        # 4. Thanh nút dưới cùng cột trái (Lưu cấu hình & Mở nhanh)
        bottom_buttons = ctk.CTkFrame(left_frame, fg_color="transparent")
        bottom_buttons.grid(row=3, column=0, padx=15, pady=(5, 15), sticky="ew")

        self.btn_save = ctk.CTkButton(
            bottom_buttons,
            text="💾 LƯU CẤU HÌNH",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=36,
            command=self._on_save_config
        )
        self.btn_save.pack(fill="x", pady=(0, 6))

        quick_links = ctk.CTkFrame(bottom_buttons, fg_color="transparent")
        quick_links.pack(fill="x")
        quick_links.grid_columnconfigure(0, weight=1)
        quick_links.grid_columnconfigure(1, weight=1)
        quick_links.grid_columnconfigure(2, weight=1)
        quick_links.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(
            quick_links, text="📝 Tin nhắn", height=28, fg_color="#334155", hover_color="#475569",
            command=lambda: self._open_file(os.path.join(engine.BASE_DIR, "message.txt"))
        ).grid(row=0, column=0, padx=(0, 2), sticky="ew")

        ctk.CTkButton(
            quick_links, text="📁 Ảnh", height=28, fg_color="#334155", hover_color="#475569",
            command=lambda: self._open_folder(os.path.join(engine.BASE_DIR, "images"))
        ).grid(row=0, column=1, padx=2, sticky="ew")

        ctk.CTkButton(
            quick_links, text="🌐 Mở Chrome", height=28, fg_color="#334155", hover_color="#475569",
            command=self._on_open_chrome
        ).grid(row=0, column=2, padx=2, sticky="ew")

        ctk.CTkButton(
            quick_links, text="🪟 Thu nhỏ", height=28, fg_color="#334155", hover_color="#475569",
            command=self._on_minimize_chrome
        ).grid(row=0, column=3, padx=(2, 0), sticky="ew")

        # ══════════════════════════════════════════════════════════
        # CỘT PHẢI: TERMINAL LOGS
        # ══════════════════════════════════════════════════════════
        right_frame = ctk.CTkFrame(self, corner_radius=10)
        right_frame.grid(row=0, column=1, padx=(8, 15), pady=15, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Header Logs
        log_header = ctk.CTkFrame(right_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=15, pady=(15, 8), sticky="ew")

        ctk.CTkLabel(
            log_header,
            text="LỊCH SỬ HOẠT ĐỘNG (REAL-TIME LOGS)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            log_header,
            text="📄 Mở File Log",
            width=90,
            height=26,
            fg_color="#334155",
            hover_color="#475569",
            command=lambda: self._open_file(engine.LOG_PATH)
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            log_header,
            text="🧹 Xóa Log",
            width=80,
            height=26,
            fg_color="#334155",
            hover_color="#475569",
            command=self._clear_logs
        ).pack(side="right")

        # Khung Text Log
        self.txt_logs = ctk.CTkTextbox(
            right_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#090d16",
            text_color="#e2e8f0",
            wrap="word"
        )
        self.txt_logs.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

    # ── Đọc / Lưu cấu hình ──────────────────────────────────────────────────
    def _load_config_into_ui(self):
        try:
            cfg = engine.load_config()

            # Schedule
            self.entry_interval.delete(0, "end")
            self.entry_interval.insert(0, str(cfg.get("interval_hours", 2)))

            self.entry_delay_min.delete(0, "end")
            self.entry_delay_min.insert(0, str(cfg.get("delay_between_groups_min", 30)))

            self.entry_delay_max.delete(0, "end")
            self.entry_delay_max.insert(0, str(cfg.get("delay_between_groups_max", 60)))

            # Minimize Chrome
            if cfg.get("minimize_chrome", True):
                self.switch_minimize.select()
            else:
                self.switch_minimize.deselect()

            # Sleep
            if cfg.get("sleep_hours_enabled", True):
                self.switch_sleep.select()
            else:
                self.switch_sleep.deselect()

            self.entry_sleep_start.delete(0, "end")
            self.entry_sleep_start.insert(0, str(cfg.get("sleep_hours_start", 0)))

            self.entry_sleep_end.delete(0, "end")
            self.entry_sleep_end.insert(0, str(cfg.get("sleep_hours_end", 6)))

            sleep_groups_str = ", ".join(cfg.get("sleep_hours_groups", []))
            self.entry_sleep_groups.delete(0, "end")
            self.entry_sleep_groups.insert(0, sleep_groups_str)

            # Telegram
            if cfg.get("telegram_enabled", True):
                self.switch_tele.select()
            else:
                self.switch_tele.deselect()

            self.entry_tele_token.delete(0, "end")
            self.entry_tele_token.insert(0, cfg.get("telegram_bot_token", ""))

            self.entry_tele_chat_id.delete(0, "end")
            self.entry_tele_chat_id.insert(0, cfg.get("telegram_chat_id", ""))

            # Groups
            self.txt_groups.delete("1.0", "end")
            groups = cfg.get("groups", [])
            self.txt_groups.insert("1.0", "\n".join(groups))

            self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙ Đã tải cấu hình thành công từ config.json.")
        except Exception as e:
            self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Lỗi đọc config: {e}")

    def _get_config_from_ui(self):
        # Đọc từ UI và trả về dict
        groups_raw = self.txt_groups.get("1.0", "end").strip().splitlines()
        groups = [g.strip() for g in groups_raw if g.strip()]

        sleep_groups_raw = self.entry_sleep_groups.get().strip().split(",")
        sleep_groups = [g.strip() for g in sleep_groups_raw if g.strip()]

        cfg = {
            "zalo_window_title": "Zalo",
            "groups": groups,
            "interval_hours": float(self.entry_interval.get().strip() or 2),
            "message_file": "message.txt",
            "images_folder": "images",
            "delay_between_actions": 1.5,
            "delay_between_groups_min": int(self.entry_delay_min.get().strip() or 30),
            "delay_between_groups_max": int(self.entry_delay_max.get().strip() or 60),
            "minimize_chrome": bool(self.switch_minimize.get()),
            "sleep_hours_enabled": bool(self.switch_sleep.get()),
            "sleep_hours_start": int(self.entry_sleep_start.get().strip() or 0),
            "sleep_hours_end": int(self.entry_sleep_end.get().strip() or 6),
            "sleep_hours_groups": sleep_groups,
            "telegram_enabled": bool(self.switch_tele.get()),
            "telegram_bot_token": self.entry_tele_token.get().strip(),
            "telegram_chat_id": self.entry_tele_chat_id.get().strip()
        }
        return cfg

    def _on_save_config(self):
        try:
            cfg = self._get_config_from_ui()
            engine.save_config(cfg)
            self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Đã lưu cấu hình thành công vào config.json!")
            messagebox.showinfo("Thành công", "Đã lưu cấu hình thành công!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {e}")

    # ── Điều khiển Start / Stop ─────────────────────────────────────────────
    def _on_start(self):
        # Lưu config trước khi chạy
        try:
            cfg = self._get_config_from_ui()
            engine.save_config(cfg)
        except Exception as e:
            messagebox.showerror("Lỗi cấu hình", f"Vui lòng kiểm tra lại cấu hình: {e}")
            return

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.worker.start()

    def _on_stop(self):
        self.btn_stop.configure(state="disabled")
        self.worker.stop()
        # Chờ 1 chút để đổi trạng thái nút Start
        self.after(2000, lambda: self.btn_start.configure(state="normal"))

    def _on_kill_all(self):
        if not messagebox.askyesno(
            "Xác nhận",
            "Bạn có chắc muốn đóng toàn bộ tiến trình Chrome, ChromeDriver và tiến trình Auto ngầm để giải phóng tài nguyên?"
        ):
            return

        self.btn_kill_all.configure(state="disabled", text="Đang tắt...")
        self.btn_stop.configure(state="disabled")

        def run_kill():
            self.worker.force_kill()
            def finish():
                self.btn_kill_all.configure(state="normal", text="⚡ TẮT TOÀN BỘ TIẾN TRÌNH NGẦM (CHROME/DRIVER)")
                self.btn_start.configure(state="normal")
                self.btn_stop.configure(state="disabled")
                messagebox.showinfo("Thành công", "Đã tắt sạch toàn bộ tiến trình Chrome & ChromeDriver ngầm!")
            self.after(0, finish)

        threading.Thread(target=run_kill, daemon=True).start()

    def update_status_badge(self, status_text):
        color_map = {
            "SẴN SÀNG": ("#334155", "#38bdf8"),
            "Đang khởi động...": ("#854d0e", "#fef08a"),
            "Đang kết nối Chrome...": ("#854d0e", "#fef08a"),
            "Chờ quét mã QR...": ("#c2410c", "#ffedd5"),
            "Đang gửi tin...": ("#166534", "#bbf7d0"),
            "Đang dừng...": ("#991b1b", "#fecaca"),
            "Đã dừng": ("#334155", "#94a3b8"),
        }
        # Kiểm tra nếu đang ở trạng thái ngủ
        bg_color, fg_color = ("#1e3a8a", "#93c5fd") if "Nghỉ" in status_text else color_map.get(status_text, ("#334155", "#ffffff"))

        def update():
            self.badge_status.configure(text=status_text, fg_color=bg_color, text_color=fg_color)
            if status_text in ("Đã dừng", "Không thể kết nối Chrome", "Chưa đăng nhập", "Lỗi cấu hình"):
                self.btn_start.configure(state="normal")
                self.btn_stop.configure(state="disabled")

        self.after(0, update)

    # ── Xử lý Log real-time ─────────────────────────────────────────────────
    def enqueue_log(self, text):
        self.log_queue.put(text)

    def _process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.txt_logs.insert("end", msg + "\n")
            self.txt_logs.see("end")
        self.after(100, self._process_log_queue)

    def _clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    # ── Test Telegram & Auto Lấy Chat ID ───────────────────────────────────
    def _on_get_telegram_chat_id(self):
        token = self.entry_tele_token.get().strip()
        if not token:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Telegram Bot Token trước!")
            return

        self.btn_get_tele_id.configure(state="disabled", text="Đang lấy...")

        def run_fetch():
            chats, err = engine.get_telegram_updates_info(token)
            
            def finish():
                self.btn_get_tele_id.configure(state="normal", text="🔍 Lấy ID")
                if err:
                    self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Lỗi lấy Chat ID: {err}")
                    messagebox.showerror("Lỗi", f"Không thể lấy thông tin từ Telegram:\n{err}")
                    return

                if not chats:
                    self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ Chưa có tương tác nào trong Bot.")
                    messagebox.showinfo(
                        "Chưa có tin nhắn trong Bot",
                        "Chưa có tin nhắn nào được gửi tới Bot!\n\n"
                        "👉 HƯỚNG DẪN:\n"
                        "1. Mở ứng dụng Telegram trên điện thoại hoặc máy tính.\n"
                        "2. Tìm tên Bot của bạn.\n"
                        "3. Nhấn nút START (hoặc gửi 1 tin nhắn bất kỳ cho Bot).\n"
                        "4. Quay lại đây và bấm nút '🔍 Lấy ID' một lần nữa để tự động điền ID số!"
                    )
                    return

                # Nếu người dùng đã nhập username trước đó, ưu tiên tìm chat khớp username
                current_input = self.entry_tele_chat_id.get().strip().lstrip("@").lower()
                chosen_chat = None
                if current_input:
                    for c in chats:
                        if c["username"].lower() == current_input or str(c["id"]) == current_input:
                            chosen_chat = c
                            break

                if not chosen_chat:
                    # Lấy chat gần nhất
                    chosen_chat = chats[0]

                target_id = chosen_chat["id"]
                display_info = f"{chosen_chat['name']} (@{chosen_chat['username']})" if chosen_chat['username'] else chosen_chat['name']
                
                self.entry_tele_chat_id.delete(0, "end")
                self.entry_tele_chat_id.insert(0, target_id)
                
                self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Đã lấy Chat ID thành công: {target_id} ({display_info})")
                
                # Tự động lưu config
                try:
                    cfg = self._get_config_from_ui()
                    engine.save_config(cfg)
                except Exception:
                    pass

                messagebox.showinfo(
                    "Thành công",
                    f"Đã tìm thấy Chat ID Telegram!\n\n"
                    f"👤 Người nhận: {display_info}\n"
                    f"🆔 Chat ID (Dạng số): {target_id}\n\n"
                    f"Đã tự động điền vào cấu hình và lưu lại. Giờ bạn có thể bấm 'Gửi Thử Thông Báo Telegram' để kiểm tra!"
                )

            self.after(0, finish)

        threading.Thread(target=run_fetch, daemon=True).start()

    def _on_test_telegram(self):
        token = self.entry_tele_token.get().strip()
        chat_id = self.entry_tele_chat_id.get().strip()

        if not token or not chat_id:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Bot Token và Chat ID trước khi test!")
            return

        self.btn_test_tele.configure(state="disabled", text="Đang kiểm tra...")

        def run_test():
            test_msg = (
                "🎉 <b>TEST THÀNH CÔNG!</b>\n"
                "Zalo Auto Messenger Pro đã kết nối thông suốt với tài khoản Telegram của bạn.\n"
                f"⏱ <i>Thời gian: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</i>"
            )
            ok, msg = engine.send_telegram_notification(token, chat_id, test_msg)
            
            def finish():
                self.btn_test_tele.configure(state="normal", text="✈ Gửi Thử Thông Báo Telegram")
                if ok:
                    self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Test Telegram thành công!")
                    messagebox.showinfo("Thành công", "Đã gửi tin nhắn thử nghiệm thành công tới Telegram của bạn!")
                else:
                    self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Test Telegram thất bại: {msg}")
                    messagebox.showerror(
                        "Lỗi kết nối Telegram",
                        f"Không thể gửi tin nhắn:\n{msg}\n\n"
                        "💡 Gợi ý: Hãy mở Telegram, tìm bot @ZaloMessengerBot và bấm /start để bot có quyền gửi tin nhắn cho bạn!"
                    )

            self.after(0, finish)

        threading.Thread(target=run_test, daemon=True).start()

    # ── Mở file / thư mục tiện ích ──────────────────────────────────────────
    def _open_file(self, file_path):
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                pass
        try:
            os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở file: {e}")

    def _open_folder(self, folder_path):
        os.makedirs(folder_path, exist_ok=True)
        try:
            os.startfile(folder_path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")

    def _on_open_chrome(self):
        threading.Thread(target=lambda: engine.launch_chrome(self.enqueue_log), daemon=True).start()

    def _on_minimize_chrome(self):
        driver = getattr(self.worker, "driver", None)
        ok = engine.minimize_chrome_window(driver, self.enqueue_log)
        if not ok:
            self.enqueue_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ Không tìm thấy cửa sổ Chrome để thu nhỏ.")

    def _on_close(self):
        if self.worker.is_running():
            if messagebox.askyesno("Xác nhận thoát", "Tiến trình Auto đang chạy ngầm. Bạn có chắc chắn muốn dừng và thoát không?"):
                self.worker.stop()
                self.destroy()
        else:
            self.destroy()


if __name__ == "__main__":
    app = ZaloAutoApp()
    app.mainloop()
