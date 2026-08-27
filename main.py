"""图纸算量工具 —— 应用入口"""
import sys
import os
import logging
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging() -> None:
    """日志落盘（~/.cad-boq-tool/logs/app.log，5MB×3 轮转），同时保留 stderr"""
    from app.config import LOG_DIR, LOG_FILE
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    log_level = os.getenv("CAD_BOQ_LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, log_level, logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)


def main():
    setup_logging()
    # Qt6 高 DPI：PassThrough 保留任意缩放系数（125%/150% 等），
    # 避免取整导致字体/控件模糊；必须在 QApplication 创建前设置。
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QFont
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("图纸算量工具")
    # 全局默认字体：优先微软雅黑，缺失时 Qt 自动按 SansSerif 回退
    default_font = QFont("Microsoft YaHei UI", 13)
    default_font.setStyleHint(QFont.SansSerif)
    app.setFont(default_font)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
