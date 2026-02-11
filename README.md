# 🧰 Python Utilities Toolbox

> ✨ **让代码服务于生活** | A collection of practical Python utilities designed to solve real-world problems.

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
![Status](https://img.shields.io/badge/Maintenance-Active-brightgreen?style=flat-square)

## 📖 简介 (Introduction)

本项目是一个 **Python 实用工具合集**，旨在通过轻量级的代码解决日常工作与生活中的具体痛点。每个工具都作为一个独立的模块存在，即插即用，方便快捷。

无论是为了提高办公效率，还是为了系统管理，这里都有可能找到你需要的“瑞士军刀”。

## 📂 工具列表 (Toolbox)

| ID | 工具名称 | 核心功能 | 技术栈 | 文档 |
| :---: | :--- | :--- | :--- | :---: |
| **001** | **论文/文章降重助手** | 智能文本改写、同义词替换、查重对比 | `requests`, `API` | [查看](./001一款论文文章降重的小工具/README.md) |
| **002** | **摄像头运动捕捉** | 实时监控、运动检测报警、自动录像 | `OpenCV`, `PyQt5` | [查看](./002一款摄像头运动捕捉小工具/README.MD) |
| **003** | **端口占用查看器** | 端口扫描、进程关联、一键结束进程 | `psutil`, `Tkinter` | [查看](./003一款查看端口占用的小工具/README.MD) |
| **004** | **定时关屏助手** | 自定义屏幕熄灭时间、电源方案管理 | `ctypes`, `Tkinter` | [查看](./004一款电脑定时关屏幕小工具/README.MD) |
| ... | *更多工具Loading...* | *Coming Soon* | ... | ... |

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
确保你的电脑已安装 **Python 3.8** 或更高版本。

```bash
# 克隆仓库
git clone <repository-url>
cd PythonProject
```

### 2. 运行工具
每个工具都位于独立的文件夹中。你可以选择以下两种方式之一运行：

*   **方式 A：直接运行源码** (推荐开发者)
    ```bash
    cd 00X某个工具目录
    pip install -r requirements.txt  # 如果有
    python 主程序.py
    ```

*   **方式 B：使用打包程序** (推荐普通用户)
    进入对应工具的 `dist` 目录，直接双击运行 `.exe` 文件即可（部分工具已提供打包版本）。

## 🛠️ 开发与扩展 (Development)

本项目采用模块化结构，欢迎提交新的工具！

### 目录规范
如果你想贡献一个新的工具，请保持以下目录结构，以维持项目的整洁与统一：

```text
00X-工具名称/
├── dist/               # (可选) PyInstaller 打包后的可执行文件
├── images/             # (推荐) 存放程序截图、演示 GIF
├── src/                # (可选) 如果代码复杂，可将源码放入 src
├── README.md           # (必须) 独立的说明文档，包含功能与用法
└── 主程序.py            # 入口文件
```

