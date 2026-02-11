import tkinter as tk
from tkinter import messagebox, ttk
import socket
import psutil
import threading
import datetime


class PortKillerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("端口占用与进程管理")
        self.root.geometry("820x540")
        self.root.minsize(760, 520)

        self.entry_map = {}
        self.all_entries = []
        self.current_pids = []
        self.all_pids = []
        self.refresh_job = None
        self.proto_var = tk.StringVar(value="全部")
        self.auto_refresh_var = tk.BooleanVar(value=False)
        self.show_cmd_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")

        self.apply_style()
        self.create_widgets()

        self.root.bind("<Return>", lambda _: self.check_port())

    def apply_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei", 14, "bold"))
        style.configure("TLabel", font=("Microsoft YaHei", 10))
        style.configure("TButton", font=("Microsoft YaHei", 10))
        style.configure("TCheckbutton", font=("Microsoft YaHei", 10))
        style.configure("TLabelframe.Label", font=("Microsoft YaHei", 10, "bold"))

    def create_widgets(self):
        container = ttk.Frame(self.root, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        title = ttk.Label(container, text="端口占用与进程管理", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        query_frame = ttk.LabelFrame(container, text="端口查询")
        query_frame.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        query_frame.columnconfigure(5, weight=1)

        ttk.Label(query_frame, text="端口号").grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")
        self.port_entry = ttk.Entry(query_frame, width=12)
        self.port_entry.grid(row=0, column=1, pady=8, sticky="w")
        ttk.Label(query_frame, text="协议").grid(row=0, column=2, padx=(12, 6), pady=8, sticky="w")
        self.proto_box = ttk.Combobox(query_frame, textvariable=self.proto_var, state="readonly", width=8)
        self.proto_box["values"] = ("全部", "TCP", "UDP")
        self.proto_box.grid(row=0, column=3, pady=8, sticky="w")

        self.check_btn = ttk.Button(query_frame, text="检查端口", command=self.check_port)
        self.check_btn.grid(row=0, column=4, padx=(12, 6), pady=8, sticky="w")
        self.refresh_btn = ttk.Button(query_frame, text="刷新", command=self.check_port)
        self.refresh_btn.grid(row=0, column=5, padx=(0, 6), pady=8, sticky="w")
        self.clear_btn = ttk.Button(query_frame, text="清空结果", command=self.clear_results)
        self.clear_btn.grid(row=0, column=6, padx=(0, 10), pady=8, sticky="w")

        options_frame = ttk.Frame(container)
        options_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.auto_refresh_chk = ttk.Checkbutton(options_frame, text="自动刷新(2秒)", variable=self.auto_refresh_var, command=self.toggle_auto_refresh)
        self.auto_refresh_chk.grid(row=0, column=0, sticky="w")
        self.show_cmd_chk = ttk.Checkbutton(options_frame, text="显示命令行", variable=self.show_cmd_var, command=self.update_detail_from_selection)
        self.show_cmd_chk.grid(row=0, column=1, padx=(12, 0), sticky="w")

        table_frame = ttk.LabelFrame(container, text="占用详情")
        table_frame.grid(row=3, column=0, sticky="nsew")
        container.rowconfigure(3, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=("pid", "name", "proto", "laddr", "raddr"), show="headings", height=10)
        self.tree.heading("pid", text="PID")
        self.tree.heading("name", text="进程")
        self.tree.heading("proto", text="协议")
        self.tree.heading("laddr", text="本地地址")
        self.tree.heading("raddr", text="远端地址")
        self.tree.column("pid", width=70, anchor="center")
        self.tree.column("name", width=160)
        self.tree.column("proto", width=70, anchor="center")
        self.tree.column("laddr", width=180)
        self.tree.column("raddr", width=180)
        self.tree.grid(row=0, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        detail_frame = ttk.LabelFrame(container, text="命令行详情")
        detail_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        detail_frame.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(detail_frame, height=3, wrap="word")
        self.detail_text.grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        action_frame = ttk.Frame(container)
        action_frame.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.kill_btn = ttk.Button(action_frame, text="结束进程", command=self.kill_process, state=tk.DISABLED)
        self.kill_btn.grid(row=0, column=0, padx=(0, 8))
        self.copy_pid_btn = ttk.Button(action_frame, text="复制PID", command=self.copy_pids, state=tk.DISABLED)
        self.copy_pid_btn.grid(row=0, column=1, padx=(0, 8))
        self.copy_cmd_btn = ttk.Button(action_frame, text="复制命令行", command=self.copy_cmdline, state=tk.DISABLED)
        self.copy_cmd_btn.grid(row=0, column=2, padx=(0, 8))

        status_bar = ttk.Label(container, textvariable=self.status_var, anchor="w")
        status_bar.grid(row=6, column=0, sticky="ew", pady=(8, 0))

    def clear_results(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.entry_map = {}
        self.all_entries = []
        self.current_pids = []
        self.all_pids = []
        self.detail_text.delete("1.0", tk.END)
        self.update_action_buttons()
        self.set_status("已清空")

    def set_status(self, text):
        self.status_var.set(text)

    def update_action_buttons(self):
        has_entries = bool(self.all_entries)
        has_selection = bool(self.tree.selection())
        self.kill_btn.config(state=tk.NORMAL if has_entries else tk.DISABLED)
        self.copy_pid_btn.config(state=tk.NORMAL if has_entries else tk.DISABLED)
        self.copy_cmd_btn.config(state=tk.NORMAL if has_selection else tk.DISABLED)

    def check_port(self, silent=False):
        self.set_status("查询中...")

        try:
            port = int(self.port_entry.get())
            if not (0 <= port <= 65535):
                if not silent:
                    messagebox.showerror("错误", "端口号必须在0-65535之间")
                self.set_status("端口号无效")
                return

            entries = self.get_entries_by_port(port, self.proto_var.get())
            self.update_table(entries)
            count = len(entries)
            now = datetime.datetime.now().strftime("%H:%M:%S")
            if count:
                self.set_status(f"端口 {port} 已占用，发现 {count} 条记录 | {now}")
            else:
                self.set_status(f"端口 {port} 未被占用 | {now}")

        except ValueError:
            if not silent:
                messagebox.showerror("错误", "请输入有效的端口号")
            self.set_status("端口号无效")
        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"发生错误: {e}")
            self.set_status(f"查询失败: {e}")

        if self.auto_refresh_var.get() and not silent:
            self.schedule_refresh()

    def update_table(self, entries):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.entry_map = {}
        self.all_entries = entries
        self.all_pids = [entry["pid"] for entry in entries if entry["pid"]]
        self.current_pids = []
        self.detail_text.delete("1.0", tk.END)
        for idx, entry in enumerate(entries):
            iid = f"row-{idx}"
            self.tree.insert("", "end", iid=iid, values=(entry["pid"], entry["name"], entry["proto"], entry["laddr"], entry["raddr"]))
            self.entry_map[iid] = entry
        self.update_action_buttons()

    def on_select(self, _event=None):
        self.update_detail_from_selection()
        selected = self.tree.selection()
        self.current_pids = [self.entry_map[i]["pid"] for i in selected if self.entry_map[i]["pid"]]
        self.update_action_buttons()

    def update_detail_from_selection(self):
        self.detail_text.delete("1.0", tk.END)
        selected = self.tree.selection()
        if not selected:
            return
        entry = self.entry_map.get(selected[0])
        if not entry:
            return
        if not self.show_cmd_var.get():
            return
        if entry["cmdline"]:
            self.detail_text.insert(tk.END, entry["cmdline"])
        else:
            self.detail_text.insert(tk.END, "无命令行或无法访问")

    def toggle_auto_refresh(self):
        if self.auto_refresh_var.get():
            self.schedule_refresh()
        else:
            if self.refresh_job:
                self.root.after_cancel(self.refresh_job)
                self.refresh_job = None
            self.set_status("已关闭自动刷新")

    def schedule_refresh(self):
        if self.refresh_job:
            self.root.after_cancel(self.refresh_job)
        self.refresh_job = self.root.after(2000, lambda: self.check_port(silent=True))

    def get_entries_by_port(self, port, proto_filter):
        results = []
        seen = set()
        for conn in psutil.net_connections(kind="inet"):
            if not conn.laddr:
                continue
            if conn.laddr.port != port:
                continue
            pid = conn.pid
            key = (pid, conn.laddr, conn.raddr, conn.type)
            if key in seen:
                continue
            seen.add(key)
            proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
            if proto_filter != "全部" and proto != proto_filter:
                continue
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
            name = "未知进程"
            cmdline = ""
            if pid:
                try:
                    process = psutil.Process(pid)
                    name = process.name()
                    cmdline = " ".join(process.cmdline())
                except psutil.Error:
                    name = "无法访问"
            results.append({
                "pid": pid,
                "name": name,
                "cmdline": cmdline,
                "proto": proto,
                "laddr": laddr,
                "raddr": raddr,
            })
        return results

    def kill_process(self):
        if self.current_pids:
            target_pids = list(self.current_pids)
        else:
            target_pids = list(self.all_pids)
        if not target_pids:
            return

        if not messagebox.askyesno("确认", f"确定要结束这些进程吗？\n{', '.join(map(str, target_pids))}"):
            return

        self.kill_btn.config(state=tk.DISABLED)
        self.set_status("正在结束进程...")

        def worker(pids):
            errors = []
            killed = []
            for pid in pids:
                if not pid:
                    continue
                try:
                    process = psutil.Process(pid)
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                    killed.append(pid)
                except psutil.NoSuchProcess:
                    killed.append(pid)
                except psutil.AccessDenied:
                    errors.append(f"PID {pid} 权限不足")
                except Exception as e:
                    errors.append(f"PID {pid} 失败: {e}")

            def finish():
                self.update_action_buttons()
                if killed:
                    messagebox.showinfo("成功", f"已结束进程: {', '.join(map(str, killed))}")
                if errors:
                    messagebox.showerror("错误", "\n".join(errors))
                self.check_port(silent=True)

            self.root.after(0, finish)

        threading.Thread(target=worker, args=(target_pids,), daemon=True).start()

    def copy_pids(self):
        selected = self.tree.selection()
        if selected:
            pids = [str(self.entry_map[i]["pid"]) for i in selected if self.entry_map[i]["pid"]]
        else:
            pids = [str(pid) for pid in self.all_pids]
        if not pids:
            messagebox.showerror("错误", "没有可复制的PID")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(",".join(pids))
        self.set_status(f"已复制 {len(pids)} 个PID")

    def copy_cmdline(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("错误", "请先选择一条记录")
            return
        entry = self.entry_map.get(selected[0])
        if not entry or not entry["cmdline"]:
            messagebox.showerror("错误", "该记录无命令行可复制")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(entry["cmdline"])
        self.set_status("已复制命令行")


def main():
    root = tk.Tk()
    app = PortKillerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
