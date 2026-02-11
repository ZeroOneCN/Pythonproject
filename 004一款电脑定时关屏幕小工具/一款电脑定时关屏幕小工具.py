import sys
import re
import subprocess
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox


class ScreenTimeoutManagerTk(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('屏幕关闭时间管理')
        self.geometry('640x360')
        self.resizable(False, False)

        self.custom_minutes_var = tk.IntVar(value=10)

        self._build_ui()
        self.refresh_status()

    # ---------- UI ----------
    def _build_ui(self):
        title = ttk.Label(self, text='屏幕关闭时间管理', font=('Microsoft YaHei', 16, 'bold'))
        title.pack(pady=12)

        status_frame = ttk.LabelFrame(self, text='当前状态')
        status_frame.pack(padx=12, pady=6, fill='x')

        self.scheme_label = ttk.Label(status_frame, text='电源方案：读取中…')
        self.scheme_label.pack(anchor='w', padx=8, pady=6)

        self.timeout_label = ttk.Label(status_frame, text='屏幕关闭时间：读取中…')
        self.timeout_label.pack(anchor='w', padx=8, pady=2)

        admin_text = '管理员权限：是' if self.is_admin() else '管理员权限：否（部分设置可能失败）'
        self.admin_label = ttk.Label(status_frame, text=admin_text)
        self.admin_label.pack(anchor='w', padx=8, pady=6)

        # 预设操作
        preset_frame = ttk.LabelFrame(self, text='快捷设置')
        preset_frame.pack(padx=12, pady=6, fill='x')

        ttk.Button(preset_frame, text='永不关闭', command=self.set_never).pack(side='left', padx=6, pady=8)
        ttk.Button(preset_frame, text='设置为 1 分钟', command=lambda: self.set_both_minutes(1)).pack(side='left', padx=6, pady=8)
        ttk.Button(preset_frame, text='恢复默认（10 分钟）', command=lambda: self.set_both_minutes(10)).pack(side='left', padx=6, pady=8)
        ttk.Button(preset_frame, text='刷新状态', command=self.refresh_status).pack(side='left', padx=6, pady=8)

        # 自定义同时设置
        custom_frame = ttk.LabelFrame(self, text='自定义设置')
        custom_frame.pack(padx=12, pady=6, fill='x')

        ttk.Label(custom_frame, text='分钟数：').pack(side='left', padx=(8, 2))
        ttk.Spinbox(custom_frame, from_=0, to=1440, textvariable=self.custom_minutes_var, width=6).pack(side='left', padx=4)
        ttk.Button(custom_frame, text='应用设置', command=self.apply_custom).pack(side='left', padx=8)
        ttk.Label(custom_frame, text='（0 表示永不关闭）').pack(side='left', padx=6)

        tip = ttk.Label(self, text='提示：涉及系统电源设置，建议以管理员权限运行。')
        tip.pack(pady=8)

    # ---------- 权限与系统调用 ----------
    @staticmethod
    def is_admin() -> bool:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def run_cmd(cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, shell=True)

    # ---------- 状态解析 ----------
    def get_scheme_name(self) -> str:
        try:
            p = self.run_cmd('powercfg /GETACTIVESCHEME')
            out = p.stdout.strip()
            if not out:
                return '未知方案（需要管理员权限或系统限制）'
            # 例子：电源方案 GUID: xxxxxxxx-...  (平衡)
            m = re.search(r'\((.+)\)', out)
            return f'{m.group(1)}' if m else out
        except Exception:
            return '读取失败'

    def get_current_timeouts(self) -> dict:
        info = {'ac_seconds': None, 'dc_seconds': None}
        try:
            p = self.run_cmd('powercfg -q SCHEME_CURRENT SUB_VIDEO VIDEOIDLE')
            out = p.stdout
            if not out:
                return info

            ac_hex = None
            dc_hex = None
            # 常见英文输出模式
            m_ac = re.search(r'Current AC Power Setting Index:\s*(0x[0-9A-Fa-f]+)', out)
            m_dc = re.search(r'Current DC Power Setting Index:\s*(0x[0-9A-Fa-f]+)', out)
            if m_ac:
                ac_hex = m_ac.group(1)
            if m_dc:
                dc_hex = m_dc.group(1)

            # 若是本地化输出或未匹配，兜底扫描包含 AC/DC 的行中的十六进制数
            if not ac_hex:
                m = re.search(r'AC[^\n]*?(0x[0-9A-Fa-f]+)', out)
                if m:
                    ac_hex = m.group(1)
            if not dc_hex:
                m = re.search(r'DC[^\n]*?(0x[0-9A-Fa-f]+)', out)
                if m:
                    dc_hex = m.group(1)

            if ac_hex:
                info['ac_seconds'] = int(ac_hex, 16)
            if dc_hex:
                info['dc_seconds'] = int(dc_hex, 16)
        except Exception:
            pass
        return info

    # ---------- 设置 ----------
    def set_timeouts(self, minutes):
        try:
            sec = max(0, int(minutes)) * 60
            r1 = subprocess.run(
                f'powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_VIDEO VIDEOIDLE {sec}',
                shell=True, check=False, capture_output=True, text=True
            )
            r2 = subprocess.run(
                f'powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_VIDEO VIDEOIDLE {sec}',
                shell=True, check=False, capture_output=True, text=True
            )
            if r1.returncode != 0 or r2.returncode != 0:
                err = (r1.stderr or '') + '\n' + (r2.stderr or '')
                raise subprocess.CalledProcessError(r1.returncode or r2.returncode, 'powercfg', err)

            # 使当前方案生效
            subprocess.run('powercfg /S SCHEME_CURRENT', shell=True, check=False)
            self.refresh_status()
            messagebox.showinfo('成功', '屏幕关闭时间已更新。')
        except subprocess.CalledProcessError as e:
            messagebox.showerror('错误', f'设置失败，可能需要管理员权限或系统限制。\n{e.stderr or e}')
        except Exception as e:
            messagebox.showerror('错误', f'设置失败：{e}')

    # ---------- 操作回调 ----------
    def set_never(self):
        self.set_timeouts(minutes=0)

    def set_both_minutes(self, minutes: int):
        self.set_timeouts(minutes=minutes)

    def apply_custom(self):
        m = int(self.custom_minutes_var.get())
        self.set_timeouts(minutes=m)

    def refresh_status(self):
        scheme = self.get_scheme_name()
        info = self.get_current_timeouts()

        self.scheme_label.config(text=f'电源方案：{scheme}')
        timeout_text = self._fmt_timeout_aggregated(info.get('ac_seconds'), info.get('dc_seconds'))
        self.timeout_label.config(text=f'屏幕关闭时间：{timeout_text}')

    @staticmethod
    def _fmt_timeout_aggregated(ac_seconds, dc_seconds):
        val = None
        if ac_seconds is not None and dc_seconds is not None:
            val = ac_seconds if ac_seconds == dc_seconds else None
        elif ac_seconds is not None:
            val = ac_seconds
        elif dc_seconds is not None:
            val = dc_seconds

        if val is None:
            if ac_seconds is None and dc_seconds is None:
                return '未知（读取失败）'
            return '已设置（系统 AC/DC 不一致）'
        if int(val) == 0:
            return '永不关闭'
        return f'{int(val) // 60} 分钟后关闭'

    # ---------- 屏幕控制 ----------
    # 其他功能模块已移除


def main():
    app = ScreenTimeoutManagerTk()
    app.mainloop()


if __name__ == '__main__':
    main()