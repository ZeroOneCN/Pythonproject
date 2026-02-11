import cv2
import sys
import os
from datetime import datetime
import numpy as np
import requests
import base64
import time
import hashlib
import zipfile
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
    QWidget, QSlider, QComboBox, QFileDialog, QMessageBox, QFrame, QSpinBox,
    QCheckBox, QGroupBox, QSizePolicy, QSpacerItem, QDialog, QFormLayout,
    QLineEdit, QDateEdit, QCalendarWidget, QPushButton, QToolButton, QMenu,
    QTimeEdit, QDoubleSpinBox
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QSize, QDate, QSettings, QTime
from PyQt5.QtGui import QIcon, QPixmap, QImage, QPalette, QColor, QFont, QPainter
from PyQt5.QtSvg import QSvgRenderer

# 默认设置
DEFAULT_RESOLUTION = (1280, 720)  # 720p
DEFAULT_FPS = 20
DEFAULT_CODEC = 'XVID'
DEFAULT_QUALITY = 85
DEFAULT_MOTION_THRESHOLD = 1500
DEFAULT_RETENTION_DAYS = 7  # 默认保留录像天数
DEFAULT_PREVIEW_FPS = 10
DEFAULT_SNAPSHOT_INTERVAL = 30
DEFAULT_SNAPSHOT_COOLDOWN = 15
DEFAULT_MAX_STORAGE_GB = 0.0
ICON_PATH = os.path.join("icons", "camera_icon.svg")

# 应用程序信息 - 用于存储设置
APP_NAME = "摄像头监控系统"
APP_ORGANIZATION = "SecurityMonitor"
APP_VERSION = "1.0.0"

# 创建应用图标对象
def create_app_icon():
    """创建应用图标对象，支持SVG格式"""
    icon = QIcon()
    svg_path = Path(ICON_PATH)
    
    if svg_path.exists():
        # 为任务栏和窗口标题生成不同尺寸的图标
        sizes = [16, 24, 32, 48, 64, 128, 256]
        
        try:
            # 加载SVG图标
            renderer = QSvgRenderer(str(svg_path))
            
            # 添加原始SVG文件
            icon.addFile(str(svg_path))
            
            # 创建不同尺寸的位图
            for size in sizes:
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.transparent)  # 透明背景
                
                # 渲染SVG到位图
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                
                # 添加到图标
                icon.addPixmap(pixmap)
                
            print(f"SVG图标已加载: {svg_path}")
            return icon
        except Exception as e:
            print(f"加载SVG图标出错: {e}")
    
    print(f"警告: 找不到图标文件 {svg_path}")
    return QIcon()

class WebhookSettingsDialog(QDialog):
    """企业微信Webhook设置对话框"""
    def __init__(self, parent=None, webhook_url=""):
        super().__init__(parent)
        self.setWindowTitle("企业微信Webhook设置")
        self.setFixedWidth(500)
        
        layout = QVBoxLayout()
        
        # 说明文本
        info_label = QLabel("设置企业微信机器人的Webhook地址，用于发送运动检测通知。")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Webhook URL输入
        form_layout = QFormLayout()
        self.webhook_input = QLineEdit(webhook_url)
        self.webhook_input.setPlaceholderText("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY")
        self.webhook_input.setMinimumWidth(400)
        form_layout.addRow("Webhook URL:", self.webhook_input)
        
        # 帮助链接
        help_text = QLabel("如何获取Webhook? <a href='https://developer.work.weixin.qq.com/document/path/91770'>查看文档</a>")
        help_text.setOpenExternalLinks(True)
        form_layout.addRow("", help_text)
        
        layout.addLayout(form_layout)
        
        # 测试按钮
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_webhook)
        layout.addWidget(self.test_button)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.cancel_btn = QPushButton("取消")
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # 信号连接
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
    def get_webhook_url(self):
        """获取设置的Webhook URL"""
        return self.webhook_input.text().strip()
        
    def test_webhook(self):
        """测试Webhook连接"""
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            QMessageBox.warning(self, "输入错误", "请输入有效的Webhook URL")
            return
            
        try:
            # 创建测试消息
            message = {
                "msgtype": "text",
                "text": {
                    "content": "这是一条来自摄像头监控系统的测试消息。"
                }
            }
            
            # 发送测试消息
            response = requests.post(webhook_url, json=message, timeout=5)
            if response.status_code != 200:
                QMessageBox.warning(self, "测试失败", f"连接失败: HTTP {response.status_code}\n{response.text}")
                return
            try:
                result = response.json()
            except Exception:
                QMessageBox.warning(self, "测试失败", f"连接失败: 返回非JSON响应\n{response.text}")
                return

            if isinstance(result, dict) and result.get("errcode") == 0:
                QMessageBox.information(self, "测试成功", "Webhook连接测试成功！")
            else:
                QMessageBox.warning(self, "测试失败", f"连接失败: {result}")
        except Exception as e:
            QMessageBox.critical(self, "测试异常", f"连接异常: {str(e)}")

class CameraView(QLabel):
    """摄像头预览控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #222; border-radius: 8px;")
        self.setText("等待摄像头连接...")
        self.setFont(QFont("Microsoft YaHei", 12))
        
    def update_frame(self, frame):
        if frame is None:
            return
            
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled_img = convert_to_qt_format.scaled(self.width(), self.height(), Qt.KeepAspectRatio)
        self.setPixmap(QPixmap.fromImage(scaled_img))
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 保持显示的图像与控件大小一致

class CleanupSettingsDialog(QDialog):
    """录像文件清理设置对话框"""
    def __init__(self, parent=None, retention_days=DEFAULT_RETENTION_DAYS):
        super().__init__(parent)
        self.setWindowTitle("录像保留设置")
        self.setFixedWidth(400)
        self.retention_days = retention_days
        
        layout = QVBoxLayout()
        
        # 录像保留时间设置
        form_layout = QFormLayout()
        self.days_spinner = QSpinBox()
        self.days_spinner.setRange(1, 365)
        self.days_spinner.setValue(self.retention_days)
        self.days_spinner.setSuffix(" 天")
        form_layout.addRow("保留录像时长:", self.days_spinner)
        
        # 下次清理时间选择
        self.next_cleanup_date = QDateEdit()
        self.next_cleanup_date.setDisplayFormat("yyyy-MM-dd")
        self.next_cleanup_date.setDate(QDate.currentDate().addDays(1))  # 默认明天
        self.next_cleanup_date.setCalendarPopup(True)
        form_layout.addRow("下次清理日期:", self.next_cleanup_date)
        
        # 立即清理按钮
        self.cleanup_now_btn = QPushButton("立即清理过期文件")
        self.cleanup_now_btn.setStyleSheet("background-color: #FF9800; color: white;")
        
        layout.addLayout(form_layout)
        layout.addWidget(self.cleanup_now_btn)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.cancel_btn = QPushButton("取消")
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # 信号连接
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.cleanup_now_btn.clicked.connect(self.cleanup_now)
        
    def get_settings(self):
        """获取设置值"""
        return {
            'retention_days': self.days_spinner.value(),
            'next_cleanup': self.next_cleanup_date.date().toString("yyyy-MM-dd")
        }
        
    def cleanup_now(self):
        """立即执行清理操作"""
        parent = self.parent()
        if parent:
            parent.cleanup_old_recordings(show_result=True)

class VideoRecorder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.recording = False
        self.out = None
        self.last_frame = None
        self.current_frame = None
        self.capture_backend = None
        self.capture_failures = 0
        self.previewing = False
        self.scheduled_recording_active = False
        self.motion_recording_active = False
        self.last_snapshot_time = 0
        self.current_video_path = None
        
        # 加载配置
        self.settings = QSettings(APP_ORGANIZATION, APP_NAME)
        self.manual_camera_id = self.get_setting('manual_camera_id', 0)
        self.preferred_backend = self.get_setting('preferred_backend', "自动")
        self.preview_fps = self.get_setting('preview_fps', DEFAULT_PREVIEW_FPS)
        self.low_load_preview = self.get_setting('low_load_preview', True)
        self.record_mode = self.get_setting('record_mode', "全时录制")
        self.schedule_start = self.get_setting('schedule_start', "08:00")
        self.schedule_end = self.get_setting('schedule_end', "20:00")
        self.snapshot_mode = self.get_setting('snapshot_mode', "关闭")
        self.snapshot_interval = self.get_setting('snapshot_interval', DEFAULT_SNAPSHOT_INTERVAL)
        self.snapshot_cooldown = self.get_setting('snapshot_cooldown', DEFAULT_SNAPSHOT_COOLDOWN)
        self.overlay_timestamp = self.get_setting('overlay_timestamp', True)
        self.overlay_device = self.get_setting('overlay_device', True)
        self.watermark_text = self.get_setting('watermark_text', "")
        self.use_daily_folder = self.get_setting('use_daily_folder', True)
        self.auto_compress = self.get_setting('auto_compress', False)
        self.max_storage_gb = self.get_setting('max_storage_gb', DEFAULT_MAX_STORAGE_GB)
        self.hardware_accel = self.get_setting('hardware_accel', False)
        
        # 创建存储目录
        self.save_dir = Path(self.get_setting('save_dir', "recordings"))
        self.save_dir.mkdir(exist_ok=True)
        
        # 录制设置
        self.resolution = self.get_setting('resolution', DEFAULT_RESOLUTION)
        self.fps = self.get_setting('fps', DEFAULT_FPS)
        self.codec = self.get_setting('codec', DEFAULT_CODEC)
        self.quality = self.get_setting('quality', DEFAULT_QUALITY)
        self.segment_duration = self.get_setting('segment_duration', 3600)  # 每小时分段（秒）
        self.segment_start_time = None
        
        # 运动检测设置
        self.motion_detection_enabled = self.get_setting('motion_detection_enabled', True)
        self.motion_threshold = self.get_setting('motion_threshold', DEFAULT_MOTION_THRESHOLD)
        self.motion_detected = False
        self.notification_sent = False
        self.last_notification_time = 0
        self.notification_cooldown = self.get_setting('notification_cooldown', 300)  # 通知冷却时间（秒）
        self.webhook_url = ""
        
        # 文件保留设置
        self.retention_days = self.get_setting('retention_days', DEFAULT_RETENTION_DAYS)
        self.next_cleanup = self.get_setting('next_cleanup', '')
        
        # 初始化摄像头ID
        self.camera_id = self.get_setting('camera_id', 0)
        self.available_cameras = self.get_available_cameras()

        self.webhook_url = self.load_webhook_url()
        if self.settings.contains('webhook_url'):
            if not self.webhook_url:
                legacy_url = self.settings.value('webhook_url', "")
                if isinstance(legacy_url, str) and legacy_url.strip():
                    self.webhook_url = legacy_url.strip()
                    self.save_webhook_url(self.webhook_url)
            self.settings.remove('webhook_url')
            self.settings.sync()
        
        # 设置应用图标
        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
            # 对于Windows，设置任务栏图标
            if os.name == 'nt':
                import ctypes
                myappid = f'{APP_ORGANIZATION}.{APP_NAME}.{APP_VERSION}'  # 应用程序ID
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.snapshot_timer = QTimer()
        self.snapshot_timer.timeout.connect(self.handle_timed_snapshot)
        
        # 初始化UI
        self.initUI()
        
        # 启动时检查是否需要清理
        self.check_auto_cleanup()
        self.start_preview()
        
    def get_setting(self, key, default_value=None):
        """获取设置值，如果不存在则返回默认值"""
        value = self.settings.value(key, default_value)
        
        # 对于一些特殊类型的值进行转换
        if isinstance(default_value, bool):
            # 确保布尔值正确解析
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
        elif isinstance(default_value, int) and not isinstance(default_value, bool):
            try:
                return int(value)
            except Exception:
                return default_value
        elif isinstance(default_value, float):
            try:
                return float(value)
            except Exception:
                return default_value
        elif isinstance(default_value, tuple) and not isinstance(value, tuple):
            # 如果是元组但存储的不是元组，尝试转换
            if isinstance(value, str):
                try:
                    # 尝试解析字符串形式的元组
                    import ast
                    return ast.literal_eval(value)
                except:
                    return default_value
        
        return value
        
    def save_setting(self, key, value):
        """保存单个设置"""
        self.settings.setValue(key, value)
        
    def save_all_settings(self):
        """保存所有设置"""
        # 保存设置到QSettings
        self.settings.setValue('save_dir', str(self.save_dir))
        self.settings.setValue('resolution', self.resolution)
        self.settings.setValue('fps', self.fps)
        self.settings.setValue('codec', self.codec)
        self.settings.setValue('quality', self.quality)
        self.settings.setValue('segment_duration', self.segment_duration)
        self.settings.setValue('motion_detection_enabled', self.motion_detection_enabled)
        self.settings.setValue('motion_threshold', self.motion_threshold)
        self.settings.setValue('notification_cooldown', self.notification_cooldown)
        self.settings.setValue('retention_days', self.retention_days)
        self.settings.setValue('next_cleanup', self.next_cleanup)
        self.settings.setValue('camera_id', self.camera_id)
        self.settings.setValue('manual_camera_id', self.manual_camera_id)
        self.settings.setValue('preferred_backend', self.preferred_backend)
        self.settings.setValue('preview_fps', self.preview_fps)
        self.settings.setValue('low_load_preview', self.low_load_preview)
        self.settings.setValue('record_mode', self.record_mode)
        self.settings.setValue('schedule_start', self.schedule_start)
        self.settings.setValue('schedule_end', self.schedule_end)
        self.settings.setValue('snapshot_mode', self.snapshot_mode)
        self.settings.setValue('snapshot_interval', self.snapshot_interval)
        self.settings.setValue('snapshot_cooldown', self.snapshot_cooldown)
        self.settings.setValue('overlay_timestamp', self.overlay_timestamp)
        self.settings.setValue('overlay_device', self.overlay_device)
        self.settings.setValue('watermark_text', self.watermark_text)
        self.settings.setValue('use_daily_folder', self.use_daily_folder)
        self.settings.setValue('auto_compress', self.auto_compress)
        self.settings.setValue('max_storage_gb', self.max_storage_gb)
        self.settings.setValue('hardware_accel', self.hardware_accel)
        self.settings.remove('webhook_url')
        
        # 确保设置被立即写入
        self.settings.sync()

    def get_webhook_store_path(self):
        base_dir = Path(sys.argv[0]).resolve().parent
        return base_dir / "webhook_config.json"

    def load_webhook_url(self):
        path = self.get_webhook_store_path()
        if not path.exists():
            return ""
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                value = data.get("webhook_url", "")
                return value.strip() if isinstance(value, str) else ""
        except Exception:
            return ""
        return ""

    def save_webhook_url(self, webhook_url):
        path = self.get_webhook_store_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as file:
                json.dump({"webhook_url": webhook_url}, file, ensure_ascii=False)
        except Exception:
            return

    def get_capture_backends(self, preferred=None):
        """获取摄像头后端优先级列表"""
        preferred_map = {
            "DSHOW": "CAP_DSHOW",
            "MSMF": "CAP_MSMF",
            "ANY": "CAP_ANY"
        }
        backends = []
        preferred_name = preferred_map.get(preferred)
        if preferred_name and hasattr(cv2, preferred_name):
            backends.append(getattr(cv2, preferred_name))
        for name in ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY"):
            if hasattr(cv2, name):
                value = getattr(cv2, name)
                if value not in backends:
                    backends.append(value)
        return backends if backends else [cv2.CAP_ANY]

    def try_read_frame(self, cap, attempts=5, delay=0.05):
        """尝试读取多帧以验证摄像头可用性"""
        for _ in range(attempts):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                return True
            time.sleep(delay)
        return False

    def apply_capture_settings(self, cap):
        """应用摄像头分辨率与帧率设置"""
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if self.hardware_accel and hasattr(cv2, "CAP_PROP_HW_ACCELERATION"):
            accel_value = getattr(cv2, "VIDEO_ACCELERATION_ANY", 1)
            cap.set(cv2.CAP_PROP_HW_ACCELERATION, accel_value)

    def open_camera(self, camera_id, set_backend=True, preferred_backend=None):
        """打开摄像头并验证可读帧"""
        for backend in self.get_capture_backends(preferred_backend):
            cap = cv2.VideoCapture(camera_id, backend)
            if not cap.isOpened():
                cap.release()
                continue
            if self.try_read_frame(cap):
                if set_backend:
                    self.capture_backend = backend
                return cap
            cap.release()

            cap = cv2.VideoCapture(camera_id, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.apply_capture_settings(cap)
            if self.try_read_frame(cap):
                if set_backend:
                    self.capture_backend = backend
                return cap
            cap.release()
        return None

    def get_daily_dir(self):
        """获取按天存储目录"""
        if not self.use_daily_folder:
            self.save_dir.mkdir(exist_ok=True)
            return self.save_dir
        date_dir = self.save_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    def get_recording_dir(self):
        """获取录像保存目录"""
        return self.get_daily_dir()

    def get_snapshot_dir(self):
        """获取截图保存目录"""
        return self.get_daily_dir()

    def apply_overlay(self, frame):
        """叠加时间戳与水印信息"""
        overlay_frame = frame.copy()
        texts = []
        if self.overlay_timestamp:
            texts.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if self.overlay_device:
            texts.append(f"Camera {self.camera_id}")
        if self.watermark_text:
            texts.append(self.watermark_text)
        if not texts:
            return overlay_frame
        y = 30
        for text in texts:
            cv2.putText(overlay_frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            y += 30
        return overlay_frame

    def save_snapshot(self, frame, prefix="snapshot"):
        """保存截图到磁盘"""
        if frame is None:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self.get_snapshot_dir()
        snapshot_path = str(snapshot_dir / f"{prefix}_{timestamp}.jpg")
        output_frame = self.apply_overlay(frame)
        cv2.imwrite(snapshot_path, output_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        self.cleanup_by_storage_limit()
        return snapshot_path

    def handle_timed_snapshot(self):
        """处理定时抓拍"""
        if self.snapshot_mode != "定时抓拍":
            return
        if self.current_frame is None:
            return
        self.save_snapshot(self.current_frame)

    def update_snapshot_timer(self):
        """更新抓拍定时器状态"""
        if self.snapshot_mode == "定时抓拍" and self.snapshot_interval > 0:
            self.snapshot_timer.start(int(self.snapshot_interval * 1000))
        else:
            self.snapshot_timer.stop()

    def is_within_schedule(self):
        """判断是否在定时录制时间段内"""
        start_time = QTime.fromString(self.schedule_start, "HH:mm")
        end_time = QTime.fromString(self.schedule_end, "HH:mm")
        now_time = QTime.currentTime()
        if not start_time.isValid() or not end_time.isValid():
            return True
        if start_time <= end_time:
            return start_time <= now_time <= end_time
        return now_time >= start_time or now_time <= end_time

    def select_best_codec(self):
        """自动选择可用编码器"""
        candidate_codecs = ["H264", "MP4V", "XVID", "MJPG"]
        test_dir = self.get_recording_dir()
        for codec in candidate_codecs:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_path = str(test_dir / f"codec_test_{codec}.avi")
            writer = cv2.VideoWriter(test_path, fourcc, max(self.fps, 1), self.resolution)
            if writer.isOpened():
                writer.release()
                Path(test_path).unlink(missing_ok=True)
                return codec
            writer.release()
            Path(test_path).unlink(missing_ok=True)
        return DEFAULT_CODEC

    def compress_video(self, video_path):
        """压缩录像文件"""
        if not self.auto_compress or not video_path:
            return
        video_file = Path(video_path)
        if not video_file.exists():
            return
        zip_path = video_file.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(video_file, arcname=video_file.name)
        video_file.unlink(missing_ok=True)

    def cleanup_by_storage_limit(self):
        """按空间阈值清理文件"""
        if not self.max_storage_gb or self.max_storage_gb <= 0:
            return
        max_bytes = int(self.max_storage_gb * 1024 * 1024 * 1024)
        files = [p for p in self.save_dir.rglob("*") if p.is_file()]
        total_size = sum(p.stat().st_size for p in files)
        if total_size <= max_bytes:
            return
        files.sort(key=lambda p: p.stat().st_mtime)
        for file_path in files:
            if total_size <= max_bytes:
                break
            try:
                size = file_path.stat().st_size
                file_path.unlink()
                total_size -= size
            except Exception:
                continue
        
    def get_available_cameras(self):
        """获取可用摄像头列表"""
        available_cameras = []
        for i in range(10):
            cap = self.open_camera(i, set_backend=False)
            if cap is not None:
                available_cameras.append(i)
                cap.release()
        return available_cameras
        
    def initUI(self):
        self.setWindowTitle("智能摄像头监控系统")
        self.setGeometry(50, 50, 1200, 850)
        self.setStyleSheet("""
            QMainWindow {background-color: #f4f6f8;}
            QLabel {color: #2f2f2f; font-family: "SimSun"; font-size: 16px;}
            QPushButton {
                background-color: #1E88E5;
                color: white;
                border: 1px solid #1565C0;
                padding: 8px 18px;
                border-radius: 8px;
                font-family: "SimSun";
                font-weight: bold;
                font-size: 17px;
                min-height: 34px;
            }
            QPushButton:hover {background-color: #1976D2;}
            QPushButton:pressed {background-color: #1565C0;}
            QPushButton:disabled {background-color: #BDBDBD; color: #757575; border: 1px solid #B0BEC5;}
            QGroupBox {
                font-family: "SimSun";
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
            }
            QComboBox, QSpinBox, QLineEdit, QTimeEdit, QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #cfd8dc;
                border-radius: 6px;
                font-family: "SimSun";
                font-size: 16px;
                min-height: 24px;
                background-color: #ffffff;
            }
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus, QTimeEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid #42A5F5;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                selection-background-color: #cfe3ff;
                selection-color: #2f2f2f;
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 10px;
                color: #2f2f2f;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e7f0ff;
                color: #2f2f2f;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #cfe3ff;
                color: #2f2f2f;
            }
            QCheckBox {
                font-family: "SimSun";
                font-size: 16px;
                spacing: 6px;
            }
            QToolButton {
                background-color: #f0f0f0;
                border: 1px solid #d5d5d5;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
                font-family: "SimSun";
                font-size: 14px;
            }
            QMenu::item {
                padding: 6px 24px 6px 24px;
            }
            QMenu::item:selected {
                background-color: #e7f0ff;
            }
        """)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(14, 14, 14, 14)
        
        # 摄像头预览区域
        self.camera_view = CameraView()
        main_layout.addWidget(self.camera_view)
        
        # 状态指示
        status_layout = QHBoxLayout()
        self.status_label = QLabel("状态: 未启动")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #1565C0;")
        self.motion_label = QLabel("未检测到运动")
        self.motion_label.setStyleSheet("color: gray; font-size: 18px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.motion_label)
        main_layout.addLayout(status_layout)
        
        # 控制区域
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(14)
        
        # 左侧控制面板 - 摄像头设置
        camera_group = QGroupBox("摄像头设置")
        camera_layout = QVBoxLayout()
        camera_layout.setSpacing(10)
        camera_layout.setContentsMargins(12, 20, 12, 12)
        
        # 摄像头选择
        camera_select_layout = QHBoxLayout()
        camera_select_layout.addWidget(QLabel("选择设备:"))
        self.camera_selector = QComboBox()
        for cam_id in self.available_cameras:
            self.camera_selector.addItem(f"摄像头 {cam_id}")
        if not self.available_cameras:
            self.camera_selector.addItem("未检测到摄像头")
            self.camera_selector.setEnabled(False)
        camera_select_layout.addWidget(self.camera_selector)
        camera_layout.addLayout(camera_select_layout)

        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("手动索引:"))
        self.manual_camera_spinner = QSpinBox()
        self.manual_camera_spinner.setRange(0, 30)
        self.manual_camera_spinner.setValue(self.manual_camera_id)
        manual_layout.addWidget(self.manual_camera_spinner)
        camera_layout.addLayout(manual_layout)

        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("后端:"))
        self.backend_selector = QComboBox()
        self.backend_selector.addItems(["自动", "DSHOW", "MSMF", "ANY"])
        backend_index = self.backend_selector.findText(self.preferred_backend)
        if backend_index >= 0:
            self.backend_selector.setCurrentIndex(backend_index)
        backend_layout.addWidget(self.backend_selector)
        camera_layout.addLayout(backend_layout)
        
        # 分辨率选择
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("分辨率:"))
        self.resolution_selector = QComboBox()
        self.resolution_selector.addItems(["1280x720 (HD)", "1920x1080 (FHD)", "640x480 (SD)", "320x240 (低)"])
        resolution_layout.addWidget(self.resolution_selector)
        camera_layout.addLayout(resolution_layout)
        
        # FPS设置
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("帧率:"))
        self.fps_spinner = QSpinBox()
        self.fps_spinner.setRange(1, 60)
        self.fps_spinner.setValue(self.fps)
        fps_layout.addWidget(self.fps_spinner)
        camera_layout.addLayout(fps_layout)

        preview_fps_layout = QHBoxLayout()
        preview_fps_layout.addWidget(QLabel("预览帧率:"))
        self.preview_fps_spinner = QSpinBox()
        self.preview_fps_spinner.setRange(1, 30)
        self.preview_fps_spinner.setValue(self.preview_fps)
        preview_fps_layout.addWidget(self.preview_fps_spinner)
        camera_layout.addLayout(preview_fps_layout)

        self.low_load_checkbox = QCheckBox("低负载预览")
        self.low_load_checkbox.setChecked(self.low_load_preview)
        camera_layout.addWidget(self.low_load_checkbox)

        self.hardware_accel_checkbox = QCheckBox("硬件加速")
        self.hardware_accel_checkbox.setChecked(self.hardware_accel)
        camera_layout.addWidget(self.hardware_accel_checkbox)
        
        camera_group.setLayout(camera_layout)
        
        # 中间控制面板 - 录制设置
        record_group = QGroupBox("录制设置")
        record_layout = QVBoxLayout()
        record_layout.setSpacing(10)
        record_layout.setContentsMargins(12, 20, 12, 12)
        
        # 保存路径选择
        save_path_layout = QHBoxLayout()
        save_path_layout.addWidget(QLabel("保存路径:"))
        self.save_path_edit = QLineEdit(str(self.save_dir))
        self.save_path_edit.setReadOnly(True)
        self.browse_button = QPushButton("浏览...")
        self.browse_button.setFixedWidth(100)
        self.browse_button.clicked.connect(self.browse_save_directory)
        save_path_layout.addWidget(self.save_path_edit, 1)  # 1是伸展因子
        save_path_layout.addWidget(self.browse_button)
        record_layout.addLayout(save_path_layout)
        
        # 编码选择
        codec_layout = QHBoxLayout()
        codec_layout.addWidget(QLabel("编码格式:"))
        self.codec_selector = QComboBox()
        self.codec_selector.addItems(["自动", "XVID", "MJPG", "H264", "MP4V"])
        
        # 设置当前编码器为配置中的值
        codec_index = self.codec_selector.findText(self.codec)
        if codec_index >= 0:
            self.codec_selector.setCurrentIndex(codec_index)
            
        codec_layout.addWidget(self.codec_selector)
        record_layout.addLayout(codec_layout)

        record_mode_layout = QHBoxLayout()
        record_mode_layout.addWidget(QLabel("录制模式:"))
        self.record_mode_selector = QComboBox()
        self.record_mode_selector.addItems(["全时录制", "运动录制", "定时录制"])
        record_mode_layout.addWidget(self.record_mode_selector)
        record_layout.addLayout(record_mode_layout)

        schedule_layout = QHBoxLayout()
        schedule_layout.addWidget(QLabel("定时段:"))
        self.schedule_start_edit = QTimeEdit()
        self.schedule_start_edit.setDisplayFormat("HH:mm")
        self.schedule_end_edit = QTimeEdit()
        self.schedule_end_edit.setDisplayFormat("HH:mm")
        schedule_layout.addWidget(self.schedule_start_edit)
        schedule_layout.addWidget(QLabel("到"))
        schedule_layout.addWidget(self.schedule_end_edit)
        record_layout.addLayout(schedule_layout)
        
        # 质量设置
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("图像质量:"))
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(self.quality)
        self.quality_value = QLabel(f"{self.quality}%")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_value.setText(f"{v}%"))
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_value)
        record_layout.addLayout(quality_layout)
        
        # 分段时长
        segment_layout = QHBoxLayout()
        segment_layout.addWidget(QLabel("分段时长:"))
        self.segment_spinner = QSpinBox()
        self.segment_spinner.setRange(1, 24)
        self.segment_spinner.setValue(self.segment_duration // 3600)
        self.segment_spinner.setSuffix(" 小时")
        segment_layout.addWidget(self.segment_spinner)
        record_layout.addLayout(segment_layout)

        storage_layout = QHBoxLayout()
        storage_layout.addWidget(QLabel("空间阈值:"))
        self.max_storage_spinner = QDoubleSpinBox()
        self.max_storage_spinner.setRange(0, 1024)
        self.max_storage_spinner.setDecimals(1)
        self.max_storage_spinner.setValue(self.max_storage_gb)
        self.max_storage_spinner.setSuffix(" GB")
        storage_layout.addWidget(self.max_storage_spinner)
        record_layout.addLayout(storage_layout)

        self.daily_folder_checkbox = QCheckBox("按天文件夹")
        self.daily_folder_checkbox.setChecked(self.use_daily_folder)
        record_layout.addWidget(self.daily_folder_checkbox)

        self.compress_checkbox = QCheckBox("自动压缩")
        self.compress_checkbox.setChecked(self.auto_compress)
        record_layout.addWidget(self.compress_checkbox)
        
        # 文件管理按钮
        self.file_management_button = QPushButton("文件管理选项")
        self.file_management_button.clicked.connect(self.show_file_management_dialog)
        record_layout.addWidget(self.file_management_button)
        
        record_group.setLayout(record_layout)
        
        # 右侧控制面板 - 运动检测
        motion_group = QGroupBox("运动检测")
        motion_layout = QVBoxLayout()
        motion_layout.setSpacing(10)
        motion_layout.setContentsMargins(12, 20, 12, 12)
        
        # 启用检测
        self.motion_checkbox = QCheckBox("启用运动检测")
        self.motion_checkbox.setChecked(self.motion_detection_enabled)
        motion_layout.addWidget(self.motion_checkbox)
        
        # 灵敏度设置
        sensitivity_layout = QHBoxLayout()
        sensitivity_layout.addWidget(QLabel("灵敏度:"))
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(500, 5000)
        self.sensitivity_slider.setValue(self.motion_threshold)
        self.sensitivity_slider.setInvertedAppearance(True)  # 反转显示，左高右低
        sensitivity_layout.addWidget(self.sensitivity_slider)
        motion_layout.addLayout(sensitivity_layout)
        
        # 通知设置
        notification_layout = QHBoxLayout()
        notification_layout.addWidget(QLabel("通知冷却:"))
        self.cooldown_spinner = QSpinBox()
        self.cooldown_spinner.setRange(1, 60)
        self.cooldown_spinner.setValue(self.notification_cooldown // 60)
        self.cooldown_spinner.setSuffix(" 分钟")
        notification_layout.addWidget(self.cooldown_spinner)
        motion_layout.addLayout(notification_layout)

        snapshot_mode_layout = QHBoxLayout()
        snapshot_mode_layout.addWidget(QLabel("抓拍模式:"))
        self.snapshot_mode_selector = QComboBox()
        self.snapshot_mode_selector.addItems(["关闭", "按键抓拍", "运动触发", "定时抓拍"])
        snapshot_mode_layout.addWidget(self.snapshot_mode_selector)
        motion_layout.addLayout(snapshot_mode_layout)

        snapshot_interval_layout = QHBoxLayout()
        snapshot_interval_layout.addWidget(QLabel("抓拍间隔:"))
        self.snapshot_interval_spinner = QSpinBox()
        self.snapshot_interval_spinner.setRange(5, 3600)
        self.snapshot_interval_spinner.setValue(self.snapshot_interval)
        self.snapshot_interval_spinner.setSuffix(" 秒")
        snapshot_interval_layout.addWidget(self.snapshot_interval_spinner)
        motion_layout.addLayout(snapshot_interval_layout)

        snapshot_cooldown_layout = QHBoxLayout()
        snapshot_cooldown_layout.addWidget(QLabel("触发冷却:"))
        self.snapshot_cooldown_spinner = QSpinBox()
        self.snapshot_cooldown_spinner.setRange(1, 600)
        self.snapshot_cooldown_spinner.setValue(self.snapshot_cooldown)
        self.snapshot_cooldown_spinner.setSuffix(" 秒")
        snapshot_cooldown_layout.addWidget(self.snapshot_cooldown_spinner)
        motion_layout.addLayout(snapshot_cooldown_layout)

        self.overlay_time_checkbox = QCheckBox("叠加时间戳")
        self.overlay_time_checkbox.setChecked(self.overlay_timestamp)
        motion_layout.addWidget(self.overlay_time_checkbox)

        self.overlay_device_checkbox = QCheckBox("叠加设备名")
        self.overlay_device_checkbox.setChecked(self.overlay_device)
        motion_layout.addWidget(self.overlay_device_checkbox)

        watermark_layout = QHBoxLayout()
        watermark_layout.addWidget(QLabel("水印:"))
        self.watermark_edit = QLineEdit(self.watermark_text)
        watermark_layout.addWidget(self.watermark_edit)
        motion_layout.addLayout(watermark_layout)
        
        # Webhook设置按钮
        self.webhook_button = QPushButton("企业微信设置")
        self.webhook_button.clicked.connect(self.show_webhook_dialog)
        self.webhook_button.setStyleSheet("background-color: #9C27B0;")  # 紫色按钮
        motion_layout.addWidget(self.webhook_button)
        
        # 保存配置按钮
        self.save_settings_button = QPushButton("保存当前设置")
        self.save_settings_button.clicked.connect(self.save_user_settings)
        self.save_settings_button.setStyleSheet("background-color: #4CAF50;")
        motion_layout.addWidget(self.save_settings_button)
        
        motion_group.setLayout(motion_layout)
        
        # 添加所有控制面板
        controls_layout.addWidget(camera_group)
        controls_layout.addWidget(record_group)
        controls_layout.addWidget(motion_group)
        
        main_layout.addLayout(controls_layout)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(14)
        buttons_layout.setContentsMargins(0, 8, 0, 0)
        
        self.start_button = QPushButton("开始监控")
        self.start_button.setIcon(QIcon.fromTheme("media-record"))
        self.start_button.clicked.connect(self.start_recording)
        self.start_button.setMinimumHeight(42)
        
        self.stop_button = QPushButton("停止监控")
        self.stop_button.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #F44336;")
        self.stop_button.setMinimumHeight(42)
        
        self.snapshot_button = QPushButton("拍摄截图")
        self.snapshot_button.setIcon(QIcon.fromTheme("camera-photo"))
        self.snapshot_button.clicked.connect(self.take_snapshot)
        self.snapshot_button.setEnabled(False)
        self.snapshot_button.setStyleSheet("background-color: #4CAF50;")
        self.snapshot_button.setMinimumHeight(42)
        
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.snapshot_button)
        
        main_layout.addLayout(buttons_layout)
        
        # 设置主窗口
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
        # 连接信号槽
        self.resolution_selector.currentIndexChanged.connect(self.update_resolution)
        self.sensitivity_slider.valueChanged.connect(self.update_motion_threshold)
        self.quality_slider.valueChanged.connect(self.update_quality)
        self.segment_spinner.valueChanged.connect(self.update_segment_duration)
        self.cooldown_spinner.valueChanged.connect(self.update_cooldown)
        self.motion_checkbox.stateChanged.connect(self.toggle_motion_detection)
        self.camera_selector.currentIndexChanged.connect(self.restart_preview)
        self.manual_camera_spinner.valueChanged.connect(self.restart_preview)
        self.backend_selector.currentIndexChanged.connect(self.restart_preview)
        self.preview_fps_spinner.valueChanged.connect(self.update_preview_settings)
        self.low_load_checkbox.stateChanged.connect(self.update_preview_settings)
        self.hardware_accel_checkbox.stateChanged.connect(self.update_preview_settings)
        self.codec_selector.currentIndexChanged.connect(self.update_codec_selection)
        self.record_mode_selector.currentIndexChanged.connect(self.update_record_mode)
        self.schedule_start_edit.timeChanged.connect(self.update_schedule_time)
        self.schedule_end_edit.timeChanged.connect(self.update_schedule_time)
        self.snapshot_mode_selector.currentIndexChanged.connect(self.update_snapshot_settings)
        self.snapshot_interval_spinner.valueChanged.connect(self.update_snapshot_settings)
        self.snapshot_cooldown_spinner.valueChanged.connect(self.update_snapshot_settings)
        self.overlay_time_checkbox.stateChanged.connect(self.update_overlay_settings)
        self.overlay_device_checkbox.stateChanged.connect(self.update_overlay_settings)
        self.watermark_edit.textChanged.connect(self.update_overlay_settings)
        self.daily_folder_checkbox.stateChanged.connect(self.update_storage_settings)
        self.compress_checkbox.stateChanged.connect(self.update_storage_settings)
        self.max_storage_spinner.valueChanged.connect(self.update_storage_settings)
        
        # 根据配置设置UI初始值
        self.apply_config_to_ui()
        
    def update_resolution(self, index):
        """更新分辨率设置"""
        resolutions = [(1280, 720), (1920, 1080), (640, 480), (320, 240)]
        self.resolution = resolutions[index]
        self.restart_preview()
        
    def update_motion_threshold(self, value):
        self.motion_threshold = value
        
    def update_quality(self, value):
        self.quality = value
        
    def update_segment_duration(self, value):
        self.segment_duration = value * 3600
        
    def update_cooldown(self, value):
        self.notification_cooldown = value * 60
        
    def toggle_motion_detection(self, state):
        self.motion_detection_enabled = state == Qt.Checked

    def update_preview_settings(self):
        """更新预览设置"""
        self.preview_fps = self.preview_fps_spinner.value()
        self.low_load_preview = self.low_load_checkbox.isChecked()
        self.hardware_accel = self.hardware_accel_checkbox.isChecked()
        self.restart_preview()

    def update_record_mode(self):
        """更新录制模式"""
        self.record_mode = self.record_mode_selector.currentText()

    def update_schedule_time(self):
        """更新定时录制时间"""
        self.schedule_start = self.schedule_start_edit.time().toString("HH:mm")
        self.schedule_end = self.schedule_end_edit.time().toString("HH:mm")

    def update_snapshot_settings(self):
        """更新抓拍设置"""
        self.snapshot_mode = self.snapshot_mode_selector.currentText()
        self.snapshot_interval = self.snapshot_interval_spinner.value()
        self.snapshot_cooldown = self.snapshot_cooldown_spinner.value()
        self.update_snapshot_timer()

    def update_overlay_settings(self):
        """更新叠加信息设置"""
        self.overlay_timestamp = self.overlay_time_checkbox.isChecked()
        self.overlay_device = self.overlay_device_checkbox.isChecked()
        self.watermark_text = self.watermark_edit.text().strip()

    def update_storage_settings(self):
        """更新存储设置"""
        self.use_daily_folder = self.daily_folder_checkbox.isChecked()
        self.auto_compress = self.compress_checkbox.isChecked()
        self.max_storage_gb = self.max_storage_spinner.value()

    def update_codec_selection(self):
        """更新编码器选择"""
        self.codec = self.codec_selector.currentText()

    def take_snapshot(self):
        """拍摄高清截图"""
        if self.current_frame is not None:
            snapshot_path = self.save_snapshot(self.current_frame)
            if snapshot_path:
                QMessageBox.information(self, "截图保存", f"截图已保存至: {snapshot_path}")
    
    def get_preferred_backend_value(self):
        """获取后端选择对应的值"""
        self.preferred_backend = self.backend_selector.currentText()
        return None if self.preferred_backend == "自动" else self.preferred_backend

    def get_selected_camera_id(self):
        """获取当前选中的摄像头索引"""
        self.manual_camera_id = self.manual_camera_spinner.value()
        if not self.available_cameras or not self.camera_selector.isEnabled():
            return self.manual_camera_id
        camera_idx = self.camera_selector.currentIndex()
        if camera_idx < 0 or camera_idx >= len(self.available_cameras):
            return self.manual_camera_id
        return self.available_cameras[camera_idx]

    def start_preview(self):
        """启动摄像头预览"""
        if self.recording:
            return
        self.previewing = True
        self.camera_id = self.get_selected_camera_id()
        preferred_backend = self.get_preferred_backend_value()
        if self.cap is None or not self.cap.isOpened():
            self.cap = self.open_camera(self.camera_id, preferred_backend=preferred_backend)
        if self.cap is None or not self.cap.isOpened():
            self.status_label.setText("错误: 无法打开摄像头")
            self.previewing = False
            return
        self.apply_capture_settings(self.cap)
        self.capture_failures = 0
        self.status_label.setText("状态: 预览中")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.snapshot_button.setEnabled(True)
        preview_fps = self.preview_fps if self.low_load_preview else self.fps
        self.timer.start(1000 // max(preview_fps, 1))
        self.update_snapshot_timer()

    def stop_preview(self, release_camera=True):
        """停止摄像头预览"""
        self.previewing = False
        if not self.recording:
            self.timer.stop()
            self.snapshot_timer.stop()
        if release_camera and self.cap is not None:
            self.cap.release()
            self.cap = None

    def restart_preview(self):
        """根据当前设置刷新预览"""
        if self.recording:
            return
        self.stop_preview(release_camera=True)
        self.start_preview()

    def start_recording(self):
        self.stop_preview(release_camera=True)
        self.update_record_mode()
        self.update_schedule_time()
        self.update_snapshot_settings()
        self.update_overlay_settings()
        self.update_storage_settings()
        self.update_codec_selection()
        self.camera_id = self.get_selected_camera_id()
        preferred_backend = self.get_preferred_backend_value()
        self.cap = self.open_camera(self.camera_id, preferred_backend=preferred_backend)
        
        if self.cap is None or not self.cap.isOpened():
            self.status_label.setText("错误: 无法打开摄像头")
            return
            
        # 设置摄像头参数
        self.apply_capture_settings(self.cap)
        
        # 获取实际设置的分辨率
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.resolution = (actual_width, actual_height)
        
        # 更新FPS
        detected_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        if detected_fps > 0:
            self.fps = detected_fps
        elif self.fps <= 0:
            self.fps = DEFAULT_FPS
        self.fps_spinner.setValue(self.fps)
        
        # 使用用户选择的保存路径
        save_path = self.save_path_edit.text()
        if save_path and Path(save_path).exists():
            self.save_dir = Path(save_path)
        self.scheduled_recording_active = False
        self.motion_recording_active = False
        self.current_video_path = None
        self.out = None
        self.motion_detected = False
        self.notification_sent = False
        self.last_notification_time = 0
        self.last_frame = None
        # 更新UI状态
        self.recording = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.snapshot_button.setEnabled(True)
        if self.record_mode == "定时录制":
            self.status_label.setText("状态: 定时等待")
        elif self.record_mode == "运动录制":
            self.status_label.setText("状态: 运动等待")
        else:
            self.status_label.setText("状态: 监控中")
            self.start_new_segment()
        
        # 启动定时器
        self.capture_failures = 0
        self.timer.start(1000 // max(self.fps, 1))
        self.update_snapshot_timer()
        
    def stop_recording(self):
        if self.recording:
            self.recording = False
            self.timer.stop()
            self.snapshot_timer.stop()
            
            if self.cap is not None:
                self.cap.release()
            
            if self.out is not None:
                self.out.release()
                self.compress_video(self.current_video_path)
                self.out = None
                self.current_video_path = None
                
            # 更新UI状态
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.snapshot_button.setEnabled(False)
            self.status_label.setText("状态: 已停止")
            self.motion_label.setText("未检测到运动")
            self.motion_label.setStyleSheet("color: gray;")
            
            # 清除摄像头预览
            self.camera_view.setText("等待摄像头连接...")
            
            # 重置状态
            self.motion_detected = False
            self.notification_sent = False
            self.current_frame = None
            self.last_frame = None
            self.scheduled_recording_active = False
            self.motion_recording_active = False
            self.start_preview()

    def start_new_segment(self):
        """开始新的视频分段"""
        if self.out is not None:
            self.out.release()
            self.compress_video(self.current_video_path)
            
        # 获取编码器
        codec_str = self.codec_selector.currentText()
        if codec_str == "自动":
            codec_str = self.select_best_codec()
        fourcc = cv2.VideoWriter_fourcc(*codec_str)
        
        # 创建文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = str(self.get_recording_dir() / f"recording_{timestamp}.avi")
        
        # 创建视频写入器
        self.out = cv2.VideoWriter(video_filename, fourcc, self.fps, self.resolution)
        
        if not self.out.isOpened():
            self.status_label.setText("错误: 无法初始化视频写入器")
            self.stop_recording()
            return
            
        self.segment_start_time = time.time()
        self.current_video_path = video_filename
        print(f"开始新的视频分段: {video_filename}, 分辨率: {self.resolution}, FPS: {self.fps}")

    def update_frame(self):
        """更新摄像头画面并处理运动检测"""
        if not self.recording and not self.previewing:
            return

        if self.cap is None or not self.cap.isOpened():
            self.camera_id = self.get_selected_camera_id()
            preferred_backend = self.get_preferred_backend_value()
            self.cap = self.open_camera(self.camera_id, preferred_backend=preferred_backend)
            if self.cap is None or not self.cap.isOpened():
                self.status_label.setText("错误: 无法打开摄像头")
                return
            
        ret, frame = self.cap.read()
        if not ret:
            self.capture_failures += 1
            self.status_label.setText("状态: 获取画面失败，正在重试")
            if self.capture_failures >= 3:
                if self.cap is not None:
                    self.cap.release()
                preferred_backend = self.get_preferred_backend_value()
                self.cap = self.open_camera(self.camera_id, preferred_backend=preferred_backend)
                if self.cap is None or not self.cap.isOpened():
                    self.status_label.setText("错误: 无法获取摄像头画面")
                    return
                self.capture_failures = 0
            return
        self.capture_failures = 0
            
        self.current_frame = frame
        output_frame = self.apply_overlay(frame)
        rgb_frame = cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB)
        self.camera_view.update_frame(rgb_frame)

        need_motion_detection = (
            self.motion_detection_enabled
            or self.record_mode == "运动录制"
            or self.snapshot_mode == "运动触发"
        )
        current_motion = False
        if need_motion_detection:
            current_motion = self.detect_motion(frame)
            self.last_frame = frame.copy()
            if current_motion:
                self.motion_label.setText("检测到运动!")
                self.motion_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.motion_label.setText("未检测到运动")
                self.motion_label.setStyleSheet("color: gray;")
        else:
            self.motion_label.setText("未检测到运动")
            self.motion_label.setStyleSheet("color: gray;")

        if self.recording and self.motion_detection_enabled:
            current_time = time.time()
            if current_motion and not self.motion_detected and not self.notification_sent:
                if current_time - self.last_notification_time > self.notification_cooldown:
                    self.send_notification(frame)
                    self.notification_sent = True
                    self.last_notification_time = current_time
            elif not current_motion and self.motion_detected:
                self.notification_sent = False
            self.motion_detected = current_motion

        if self.recording and self.snapshot_mode == "运动触发" and current_motion:
            current_time = time.time()
            if current_time - self.last_snapshot_time >= self.snapshot_cooldown:
                self.save_snapshot(frame)
                self.last_snapshot_time = current_time

        if self.recording:
            if self.record_mode == "定时录制":
                if self.is_within_schedule():
                    if not self.scheduled_recording_active or self.out is None:
                        self.start_new_segment()
                        self.scheduled_recording_active = True
                    self.out.write(output_frame)
                else:
                    if self.out is not None:
                        self.out.release()
                        self.compress_video(self.current_video_path)
                        self.out = None
                        self.current_video_path = None
                    self.scheduled_recording_active = False
                    self.status_label.setText("状态: 定时等待")
            elif self.record_mode == "运动录制":
                if current_motion:
                    if not self.motion_recording_active or self.out is None:
                        self.start_new_segment()
                        self.motion_recording_active = True
                    self.out.write(output_frame)
                else:
                    if self.out is not None:
                        self.out.release()
                        self.compress_video(self.current_video_path)
                        self.out = None
                        self.current_video_path = None
                    self.motion_recording_active = False
                    self.status_label.setText("状态: 运动等待")
            else:
                if self.out is None:
                    self.start_new_segment()
                if self.out is not None:
                    self.out.write(output_frame)

            if self.out is not None and time.time() - self.segment_start_time > self.segment_duration:
                self.start_new_segment()

    def detect_motion(self, current_frame):
        """改进的运动检测算法"""
        if self.last_frame is None:
            return False
            
        # 转灰度和平滑处理
        gray_current = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        gray_current = cv2.GaussianBlur(gray_current, (21, 21), 0)
        
        gray_last = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2GRAY)
        gray_last = cv2.GaussianBlur(gray_last, (21, 21), 0)
        
        # 计算帧差
        frame_diff = cv2.absdiff(gray_current, gray_last)
        thresh = cv2.threshold(frame_diff, 30, 255, cv2.THRESH_BINARY)[1]
        
        # 膨胀操作更好地连接区域
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 用户可调节的阈值
        for contour in contours:
            if cv2.contourArea(contour) > self.motion_threshold:
                return True
                
        return False

    def send_notification(self, frame):
        """发送企业微信通知，使用高质量图片"""
        if not self.recording:
            return
        # 检查是否配置了webhook URL
        webhook_url = self.webhook_url
        if not webhook_url:
            print("未配置企业微信Webhook，无法发送通知")
            self.status_label.setText("状态: 监控中 (未配置通知)")
            return
        
        screenshot_path = self.save_snapshot(frame, prefix="motion")
        if not screenshot_path:
            return
        
        # 发送企业微信通知
        with open(screenshot_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            md5_hash = hashlib.md5(image_data).hexdigest()
        
        message = {
            "msgtype": "image",
            "image": {
                "base64": base64_image,
                "md5": md5_hash
            }
        }
        
        try:
            response = requests.post(webhook_url, json=message, timeout=8)
            if response.status_code != 200:
                print(f"发送失败: HTTP {response.status_code} {response.text}")
                self.status_label.setText("状态: 监控中 (通知发送失败)")
                return

            try:
                result = response.json()
            except Exception:
                print(f"发送失败: 返回非JSON响应 {response.text}")
                self.status_label.setText("状态: 监控中 (通知发送失败)")
                return

            if isinstance(result, dict) and result.get("errcode") == 0:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"通知已发送 - {timestamp}")
                self.status_label.setText("状态: 监控中 (已发送通知)")
                return

            print(f"发送失败: {result}")
            self.status_label.setText("状态: 监控中 (通知发送失败)")
        except Exception as e:
            print(f"发送通知异常: {e}")
            self.status_label.setText("状态: 监控中 (通知发送异常)")

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        self.stop_recording()
        event.accept()

    def check_auto_cleanup(self):
        """检查是否需要自动清理过期文件"""
        if not self.next_cleanup:
            return
            
        try:
            next_date = QDate.fromString(self.next_cleanup, "yyyy-MM-dd")
            if next_date <= QDate.currentDate():
                # 如果已到达或超过计划清理日期，执行清理
                self.cleanup_old_recordings()
                
                # 更新下一次清理日期(当前日期+7天)
                self.next_cleanup = QDate.currentDate().addDays(7).toString("yyyy-MM-dd")
                self.save_all_settings()
        except Exception as e:
            print(f"检查自动清理时出错: {e}")

    def cleanup_old_recordings(self, show_result=False):
        """清理过期文件"""
        if self.retention_days <= 0:
            return
            
        try:
            # 计算截止日期(当前日期减去保留天数)
            cutoff_date = datetime.now().timestamp() - (self.retention_days * 24 * 60 * 60)
            cleaned_count = 0
            cleaned_size = 0
            
            for file_path in self.save_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                file_time = file_path.stat().st_mtime
                if file_time < cutoff_date:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_count += 1
                    cleaned_size += file_size
                    
            if show_result:
                size_mb = cleaned_size / (1024 * 1024)
                QMessageBox.information(
                    self, 
                    "清理完成", 
                    f"已清理 {cleaned_count} 个文件，释放 {size_mb:.2f} MB 空间。"
                )
                
            print(f"清理完成: 删除了 {cleaned_count} 个文件，释放了 {cleaned_size / (1024*1024):.2f} MB 空间")
            
        except Exception as e:
            print(f"清理过期文件时出错: {e}")
            if show_result:
                QMessageBox.warning(self, "清理失败", f"清理过程中出错: {e}")

    def apply_config_to_ui(self):
        """根据配置设置UI初始值"""
        # 设置分辨率选择器
        resolution_text = None
        if self.resolution[0] == 1280 and self.resolution[1] == 720:
            resolution_text = "1280x720 (HD)"
        elif self.resolution[0] == 1920 and self.resolution[1] == 1080:
            resolution_text = "1920x1080 (FHD)"
        elif self.resolution[0] == 640 and self.resolution[1] == 480:
            resolution_text = "640x480 (SD)"
        elif self.resolution[0] == 320 and self.resolution[1] == 240:
            resolution_text = "320x240 (低)"
            
        if resolution_text:
            index = self.resolution_selector.findText(resolution_text)
            if index >= 0:
                self.resolution_selector.setCurrentIndex(index)
                
        self.fps_spinner.setValue(self.fps)
        self.codec_selector.setCurrentIndex(self.codec_selector.findText(self.codec))
        self.quality_slider.setValue(self.quality)
        self.segment_spinner.setValue(self.segment_duration // 3600)
        self.cooldown_spinner.setValue(self.notification_cooldown // 60)
        self.motion_checkbox.setChecked(self.motion_detection_enabled)
        self.sensitivity_slider.setValue(self.motion_threshold)
        self.manual_camera_spinner.setValue(self.manual_camera_id)
        backend_index = self.backend_selector.findText(self.preferred_backend)
        if backend_index >= 0:
            self.backend_selector.setCurrentIndex(backend_index)
        self.preview_fps_spinner.setValue(self.preview_fps)
        self.low_load_checkbox.setChecked(self.low_load_preview)
        self.hardware_accel_checkbox.setChecked(self.hardware_accel)
        record_mode_index = self.record_mode_selector.findText(self.record_mode)
        if record_mode_index >= 0:
            self.record_mode_selector.setCurrentIndex(record_mode_index)
        self.schedule_start_edit.setTime(QTime.fromString(self.schedule_start, "HH:mm"))
        self.schedule_end_edit.setTime(QTime.fromString(self.schedule_end, "HH:mm"))
        snapshot_mode_index = self.snapshot_mode_selector.findText(self.snapshot_mode)
        if snapshot_mode_index >= 0:
            self.snapshot_mode_selector.setCurrentIndex(snapshot_mode_index)
        self.snapshot_interval_spinner.setValue(self.snapshot_interval)
        self.snapshot_cooldown_spinner.setValue(self.snapshot_cooldown)
        self.overlay_time_checkbox.setChecked(self.overlay_timestamp)
        self.overlay_device_checkbox.setChecked(self.overlay_device)
        self.watermark_edit.setText(self.watermark_text)
        self.max_storage_spinner.setValue(self.max_storage_gb)
        self.daily_folder_checkbox.setChecked(self.use_daily_folder)
        self.compress_checkbox.setChecked(self.auto_compress)

    def browse_save_directory(self):
        """打开文件夹选择对话框"""
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", str(self.save_dir))
        if directory:
            self.save_dir = Path(directory)
            self.save_path_edit.setText(directory)
            # 确保目录存在
            self.save_dir.mkdir(exist_ok=True)

    def show_file_management_dialog(self):
        """显示文件管理对话框"""
        dialog = CleanupSettingsDialog(self, self.retention_days)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.retention_days = settings['retention_days']
            self.next_cleanup = settings['next_cleanup']
            # 更新配置
            self.save_all_settings()

    def save_user_settings(self):
        """保存用户设置"""
        self.save_all_settings()
        QMessageBox.information(self, "设置保存", "您的设置已成功保存。")

    def show_webhook_dialog(self):
        """显示企业微信设置对话框"""
        dialog = WebhookSettingsDialog(self, self.webhook_url)
        if dialog.exec_() == QDialog.Accepted:
            webhook_url = dialog.get_webhook_url()
            self.webhook_url = webhook_url
            self.save_webhook_url(self.webhook_url)

def main():
    """程序入口"""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置应用程序信息 - 用于QSettings和桌面快捷方式
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("智能摄像头监控系统")
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)
    
    # 设置应用图标 - 确保在所有地方显示
    app_icon = create_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
        
        # 对于Windows，设置任务栏图标ID
        if os.name == 'nt':
            import ctypes
            myappid = f'{APP_ORGANIZATION}.{APP_NAME}.{APP_VERSION}'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    # 创建并显示主窗口
    window = VideoRecorder()
    window.show()
    
    # 应用程序循环
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
