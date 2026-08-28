"""主窗口：组装画布 / 图层树 / BOQ 表格 / 映射面板 / 工具栏"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
                               QComboBox, QPushButton, QListWidget, QListWidgetItem,
                               QGridLayout, QMenu, QApplication,
                               QFileDialog, QMessageBox, QLabel, QProgressDialog, QTabWidget,
                               QDialog, QInputDialog, QLineEdit, QFrame)

from .. import db
from .. import mapping as map_svc
from .. import measure, report
from ..cad import cad_parser as cad_parser
from ..cad import dwg as dwg_svc
from ..boq import boq_parser as boq_parser
from ..models import BoqItem, LayerInfo, BlockInfo
from .canvas import CanvasView
from .layer_tree import LayerTreeWidget
from .boq_table import BoqTable
from .mapping_panel import MappingPanel
from .legend_panel import LegendPanel
from .binding_workbench import BindingWorkbench
from .project_properties import ProjectPropertiesPanel
from .canvas_toolbar import CanvasToolbar
from .selection_bar import SelectionBar
from .history_panel import HistoryPanel
from .entity_properties import EntityPropertiesPanel
from . import theme as T
from .ui_utils import save_window_state, restore_window_state

# ===== v2 浅色主题（由 theme.py 生成） =====
LIGHT_QSS = T.generate_main_qss()

logger = logging.getLogger(__name__)

# ===== F1 使用说明（P1-13 富文本 + 快捷键表） =====
_HELP_HTML = """
<div style="font-family:'Microsoft YaHei UI','微软雅黑',sans-serif; color:#1F2733; font-size:13px;">

<h3 style="margin:4px 0 8px;">图纸算量工具 · 使用说明</h3>

<h4 style="margin:10px 0 4px;">基本流程（4 步）</h4>
<ol style="margin-top:2px;">
<li>顶部「<b>新建</b>」创建项目，输入名称即可</li>
<li>「<b>打开图纸</b>」载入 DWG/DXF；或「更多 → 批量导入文件夹」整批载入</li>
<li>「<b>更多 → 导入 BOQ</b>」导入 Excel 工程量清单</li>
<li>选中清单条目 → 图纸上操作完成关联 → 「<b>导出算量清单</b>」(Excel)</li>
</ol>

<h4 style="margin:10px 0 4px;">图纸上的操作</h4>
<ul style="margin-top:2px;">
<li><b>双击</b>图形 / <b>Shift+拖拽框选</b> → 关联到当前 BOQ 条目</li>
<li><b>拾取</b>：点选单个实体；<b>图层/块</b>模式：在左侧图层树/块树右键批量关联</li>
<li><b>删除映射</b>会先弹确认框；误删可按 <b>Ctrl+Z</b> 撤销回最近一次关联/删除</li>
<li>左边「图层」树收起后，可在右上「模式」三点菜单切换拾取/图层/块</li>
</ul>

<h4 style="margin:10px 0 4px;">BOQ 清单页</h4>
<ul style="margin-top:2px;">
<li>顶部<b>搜索框</b>：按编号/描述/单位过滤并高亮命中行</li>
<li>每行可改<b>计量规则</b>（长度/面积/数量）与<b>比例因子</b>，改动自动重算（带防抖）</li>
</ul>

<h4 style="margin:10px 0 4px;">绑定工作台 &amp; AI 算量</h4>
<ul style="margin-top:2px;">
<li>「<b>AI 算量</b>」→ 对当前图纸自动识别设备并生成候选；结果在「更多 → AI 算量结果」复核</li>
<li>「绑定工作台」审核队列每行有<b>行内 ✓确认 / ✗拒绝</b>按钮，无需先选中行</li>
<li>LLM 增强 / 补充分类需配置后端：点左下角「<b>LLM: —</b>」标签或「更多 → LLM 设置…」</li>
</ul>

<h4 style="margin:14px 0 6px;">快捷键</h4>
<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse; font-size:13px;">
<tr style="background:#EEF1F5;"><th style="text-align:left;">按键</th><th style="text-align:left;">功能</th></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;N</b></td><td>新建项目</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;O</b></td><td>打开图纸</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;S</b></td><td>导出算量清单 (Excel)</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;1 … 6</b></td><td>切换右侧工作区：1 绑定工作台 / 2 BOQ 清单 / 3 计量 / 4 图例标定 / 5 实体属性 / 6 项目属性</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;B</b></td><td>折叠/展开左侧面板</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;Alt&nbsp;+&nbsp;B</b></td><td>折叠/展开右侧面板</td></tr>
<tr><td><b>Ctrl&nbsp;+&nbsp;Z</b></td><td>撤销最近一次关联/删映射（输入框中则撤销文字）</td></tr>
<tr><td><b>滚轮</b></td><td>画布缩放</td></tr>
<tr><td><b>中键拖拽</b></td><td>画布平移</td></tr>
<tr><td><b>Shift&nbsp;+&nbsp;左键</b></td><td>框选多个实体</td></tr>
<tr><td><b>F1</b></td><td>使用说明（本页）</td></tr>
</table>

<p style="color:#889099; font-size:12px; margin-top:10px;">
问题排查：解析 DWG 失败请安装 ODA File Converter（免费）并重开；
LLM 不可用请检查「更多 → LLM 设置…」中的后端地址与服务状态。
</p>
</div>
"""

# rail 按钮序 → right_tabs 页签索引（v3 布局：绑定0/清单1/计量2/实体属性4/记录6）
# 图例标定(3) / 项目属性(5) 不在 rail，经「更多 ▾」菜单或 Ctrl+1..6 到达。
RAIL_TAB_INDEX = [0, 1, 2, 4, 6]


class _AiTakeoffWorker(QThread):
    """AI 算量后台线程（单图）"""
    progress = Signal(str, float, str)
    finished_ok = Signal(object)        # TakeoffResult
    failed = Signal(str)

    def __init__(self, path: str, config, legend: dict = None):
        super().__init__(parent=None)
        self._path = path
        self._config = config
        self._legend = legend

    def run(self):
        try:
            from app.takeoff.orchestrator import takeoff_pipeline
            def cb(phase, p, msg):
                self.progress.emit(phase, p, msg)
            result = takeoff_pipeline(self._path, config=self._config,
                                      progress_cb=cb, legend=self._legend)
            self.finished_ok.emit(result)
        except Exception as e:
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _AiTakeoffFolderWorker(QThread):
    """AI 算量后台线程（文件夹）"""
    progress = Signal(str, float, str)
    finished_ok = Signal(object)        # FolderPipelineResult
    failed = Signal(str)

    def __init__(self, folder, config, legend: dict = None):
        super().__init__(parent=None)
        self._folder = folder
        self._config = config
        self._legend = legend

    def run(self):
        try:
            from app.takeoff.folder_pipeline import run_folder_pipeline
            def cb(phase, p, msg):
                self.progress.emit(phase, p, msg)
            result = run_folder_pipeline(self._folder, config=self._config,
                                         progress_cb=cb, legend=self._legend)
            self.finished_ok.emit(result)
        except Exception as e:
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _ImportFolderWorker(QThread):
    """批量导入图纸文件夹（递归，缓存优先）后台线程"""
    progress = Signal(int, int, str, str)      # (done, total, filename, status)
    finished_ok = Signal(dict)                 # stats
    failed = Signal(str)

    def __init__(self, project_id: int, folder: str, cancel_event=None):
        super().__init__(parent=None)
        self._project_id = project_id
        self._folder = folder
        self._cancel_event = cancel_event

    def run(self):
        try:
            from app.import_folder import import_folder
            stats = import_folder(
                self._project_id, self._folder,
                progress_cb=lambda d, t, n, s: self.progress.emit(d, t, n, s),
                cancel_event=self._cancel_event)
            self.finished_ok.emit(stats)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _BatchReparseWorker(QThread):
    """批量重新解析全部图纸（转换池 + 解析进程池）后台线程。

    cancel_event 由 UI 持有：进度对话框「取消」→ event.set() →
    编排器在文件边界协作停止。
    """
    progress = Signal(int, int, str, str)      # (done, total, filename, status)
    finished_ok = Signal(dict)                 # stats
    failed = Signal(str)

    def __init__(self, project_id: int, cancel_event, workers: int = None):
        super().__init__(parent=None)
        self._project_id = project_id
        self._cancel_event = cancel_event
        self._workers = workers

    def run(self):
        try:
            from app.batch_reparse import BatchReparseJob
            job = BatchReparseJob(
                self._project_id,
                progress_cb=lambda d, t, n, s: self.progress.emit(d, t, n, s),
                cancel_event=self._cancel_event,
                workers=self._workers,
            )
            stats = job.run()
            self.finished_ok.emit(stats)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _VacuumWorker(QThread):
    """数据库 VACUUM 后台线程（P1-2）：大库（GB 级）耗时数秒~数十秒，不能卡 UI。"""
    finished_ok = Signal(dict)     # {"before_bytes", "after_bytes", "freed_bytes", "duration_ms"}
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            res = db.vacuum_database()
            self.finished_ok.emit(res)
        except Exception as e:
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _SheetLoadWorker(QThread):
    """切图数据后台加载（P1-1）：blocks_json 解析 + DB 实体/图层统计不进 UI 线程。

    注意：QGraphicsItem 只能在 GUI 线程创建/删除，因此真正的重头
    （canvas.build 逐实体建图形项）仍回主线程分批执行——配合
    canvas.build 的 progress_cb / cancel_event，UI 显示进度条且不冻结。
    本类只把「DB 读取 + JSON 反序列化」挪到子线程（实测 ~0.7s 的卡顿来源）。
    """
    data_ready = Signal(object)      # dict: {blocks, entities, layer_colors, layers, blocks_info}
    failed = Signal(int, str)        # (sheet_id, err)

    def __init__(self, sheet_id: int, blocks_json: str, parent=None):
        super().__init__(parent)
        self._sheet_id = sheet_id
        self._blocks_json = blocks_json

    def run(self):
        try:
            blocks = json.loads(self._blocks_json) if self._blocks_json else {}
            entities = db.get_entities(self._sheet_id)
            layer_colors = db.layer_color_map(self._sheet_id)
            layers = db.distinct_layers(self._sheet_id)
            blocks_info = db.distinct_blocks(self._sheet_id)
            self.data_ready.emit({
                "blocks": blocks,
                "entities": entities,
                "layer_colors": layer_colors,
                "layers": layers,
                "blocks_info": blocks_info,
            })
        except Exception as e:
            import traceback
            self.failed.emit(self._sheet_id, f"{e}\n{traceback.format_exc()}")
        finally:
            # 子线程连接用完即关（线程注销，防 sqlite 连接泄漏）
            try:
                db._close_thread_conn()
            except Exception:
                pass


class _ParseCancelled(Exception):
    """用户取消解析：在进度回调中抛出，worker 静默退出。"""


class ParseWorker(QThread):
    """后台解析 DWG/DXF：避免大图阻塞 UI。

    cancel_event（threading.Event）设置后：
      - 尚未开始/命中缓存：直接返回不发送 done；
      - 解析中：下一次进度回调抛出 _ParseCancelled 中止解析。
    """
    progress = Signal(int, int)      # (done, total)；done=-1 表示进入块收集阶段
    done = Signal(str, object)       # (dxf_path, ParsedDrawing)
    failed = Signal(str)

    def __init__(self, src_path: str, parent=None, cancel_event=None):
        super().__init__(parent)
        self.src_path = src_path
        self._cancel_event = cancel_event

    def run(self):
        try:
            if self._cancel_event is not None and self._cancel_event.is_set():
                return
            dxf_path = self.src_path
            # V2：解析缓存命中则跳过解析（二次打开 <1s）
            from ..cad import parse_cache
            cached = parse_cache.get_cached_drawing(self.src_path)
            if cached is not None:
                if self._cancel_event is None or not self._cancel_event.is_set():
                    self.done.emit(self.src_path, cached)
                return
            if self.src_path.lower().endswith(".dwg"):
                # 秒级探测 ezdwg 可解码性：失败图立即走 ODA 回退，省去 20-40s 完整解析等待
                from ..cad import reader as cad_reader
                probe_err = cad_reader.probe_dwg_support(self.src_path)
                if probe_err:
                    import logging
                    logging.warning("ezdwg 探测不可读（秒级判定）: %s | %s",
                                    self.src_path, probe_err)
                    self._direct_err = probe_err
                else:
                    # 优先 ezdwg 直读（无需 ODA，parse_dxf 内部按扩展名自动选后端）
                    try:
                        drawing = cad_parser.parse_dxf(self.src_path, self._cb)
                        parse_cache.cache_drawing(self.src_path, drawing)
                        self.done.emit(self.src_path, drawing)
                        return
                    except Exception as direct_err:  # noqa: BLE001
                        import logging
                        logging.exception("ezdwg 直读失败（将尝试 ODA 回退）: %s", self.src_path)
                        self._direct_err = str(direct_err)
                # 回退：ODA File Converter 转 DXF
                tmp = tempfile.mkdtemp(prefix="cadboq_")
                try:
                    conv = dwg_svc.convert_dwg_to_dxf(self.src_path, tmp)
                except Exception as conv_err:  # noqa: BLE001
                    conv = None
                    self._oda_err = str(conv_err)
                if not conv:
                    # 错误分类：ezdwg 解码器对部分 AC1032（R2018）压缩流不支持
                    hint = ""
                    err = getattr(self, '_direct_err', '未知原因')
                    if "format error" in err or "opcode" in err or "page" in err:
                        hint = (
                            "\n\n原因：该 DWG 使用 ezdwg 暂不支持的压缩编码（R2004+ 变体）。\n"
                            "已识别 26/39 张同类图纸受影响（与本机无关，是解析库能力边界）。\n"
                            "解决：安装 ODA File Converter（免费，工业标准转换器）后即可打开。")
                    self.failed.emit(
                        f"DWG 解析失败：ezdwg 直读出错（{err}），"
                        f"且 ODA 转换不可用（{getattr(self, '_oda_err', '未找到 ODA File Converter')}）。\n\n"
                        "解决方案（任选其一）：\n"
                        "1. 安装 ODA File Converter（免费）: "
                        "https://www.opendesign.com/guestfiles/oda_file_converter\n"
                        "   默认安装到 C:\\Program Files\\ODA\\ODAFileConverter 即可自动识别"
                        f"{hint}\n"
                        "2. 在 AutoCAD/浩辰中把 DWG 另存为 DXF 后再打开")
                    return
                dxf_path = conv
            drawing = cad_parser.parse_dxf(dxf_path, self._cb)
            parse_cache.cache_drawing(self.src_path, drawing)
            self.done.emit(dxf_path, drawing)
        except _ParseCancelled:
            logger.info("parse cancelled: %s", self.src_path)
            return
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))

    def _cb(self, done: int, total: int):
        if self._cancel_event is not None and self._cancel_event.is_set():
            raise _ParseCancelled()
        self.progress.emit(done, total)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(LIGHT_QSS)
        self.setWindowTitle("图纸算量工具")
        # 屏幕适配：初始尺寸 clamp 到可用区域
        avail = self.screen().availableGeometry() if self.screen() else None
        if avail:
            init_w = min(T.MAIN_WINDOW_DEFAULT_W, int(avail.width() * 0.95))
            init_h = min(T.MAIN_WINDOW_DEFAULT_H, int(avail.height() * 0.95))
        else:
            init_w, init_h = T.MAIN_WINDOW_DEFAULT_W, T.MAIN_WINDOW_DEFAULT_H
        self.resize(init_w, init_h)
        self.setMinimumSize(T.MAIN_WINDOW_MIN_W, T.MAIN_WINDOW_MIN_H)

        self._project_id = None
        self._sheet_id = None
        self._sheet_load_seq = 0          # 切图序号：丢弃过期后台加载结果（P1-1）
        self._sheet_cancel_event = None   # 取消当前正在构建的画布（P1-1）
        self._reparse_sid = None  # 重新解析模式：>0 时 _on_parse_done 更新而非新建
        self._current_item_id = None
        self._current_item_desc = ""
        self._current_blocks = {}
        self._dark = False
        self._fullscreen = False
        self._saved_geometry = None
        self._mode = "pick"   # 拾取/图层/块
        self._stat_entities = 0
        self._stat_layers = 0
        self._stat_boq = 0
        self._pending_locate_name = None  # 跨图纸定位时暂存块名/图层名
        # 计量重算防抖（P0-5）
        self._recalc_timer: QTimer | None = None
        self._recalc_pending_item: int | None = None
        self._busy = False
        # 状态消息中心（P0-7）：环形记录 statusBar 消息
        self._history: list[tuple[float, str]] = []
        # 撤销栈（P0-8）：最近关联/删除映射可 Ctrl+Z 撤销
        self._undo_stack: list[tuple] = []
        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._register_shortcuts()
        db.init_db()
        self._reload_projects()
        self._restore_settings()
        self._maybe_show_welcome()
        # 启动后短暂延迟检查数据库碎片（P1-2）：空闲页占比过高 → 提示整理
        QTimer.singleShot(800, self._check_db_fragmentation)

    def _maybe_show_welcome(self):
        """首次启动（且尚无任何项目）时展示一次性引导；离屏测试环境跳过。"""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        s = self._settings()
        if s.value("welcome_shown", False, type=bool):
            return
        s.setValue("welcome_shown", True)
        if self._project_id is not None:
            return  # 已有项目：不打断
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("欢迎使用 图纸算量工具")
        box.setText(
            "使用流程（4 步）：\n\n"
            "1. 点击顶部「新建」创建项目\n"
            "2. 「打开图纸」载入 DWG/DXF（或「更多 → 批量导入文件夹」）\n"
            "3. 「更多 → 导入 BOQ」导入 Excel 工程量清单\n"
            "4. 「AI 算量」自动识别设备并生成候选；或用「绑定工作台」人工复核确认\n\n"
            "右侧工作区有 7 个页面：绑定 / 清单 / 计量 / 属性 / 记录（右栏\n"
            "rail），图例标定与项目属性在「更多 ▾」菜单（亦可 Ctrl+1..6 切换）。\n"
            "更多说明见「更多 → 使用说明」(F1)。")
        box.setStandardButtons(QMessageBox.Ok)
        box.setWindowModality(Qt.NonModal)
        box.show()

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 面板提前实例化：_build_topbar 的 AI 菜单引用了 binding_workbench /
        # _more_actions，而各面板是无副作用的纯容器，先建不影响后续布局。
        self._more_actions: dict[str, object] = {}
        self.mapping_panel = MappingPanel()
        self.legend_panel = LegendPanel()
        self.binding_workbench = BindingWorkbench()
        self.project_properties = ProjectPropertiesPanel()
        self.entity_properties = EntityPropertiesPanel()
        self.history_panel = HistoryPanel()

        # 顶部品牌栏（v2：替代菜单栏）
        root.addWidget(self._build_topbar())

        # 主体：三栏 splitter
        split_main = QSplitter(Qt.Horizontal)
        self._split_main = split_main

        # 左栏（main.html 1:1）：「图纸 / Sheet」头部行 + 搜索 + 卡片式图纸列表 + 图层/块
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        # 头部行：标题 + 添加/删除图标按钮（h-11）
        head = QWidget()
        head.setObjectName("panelHeader")
        hh = QHBoxLayout(head)
        hh.setContentsMargins(12, 0, 8, 0)
        hh.setSpacing(2)
        t_sheets = QLabel("图纸 / Sheet")
        t_sheets.setObjectName("panelTitle")
        hh.addWidget(t_sheets)
        hh.addStretch(1)

        def _fluent(key: str, fallback: str) -> str:
            return T.ICONS.get(key, fallback) if T.icon_font_family() else fallback

        self.btn_add_sheet = QPushButton(_fluent("add", "＋"))
        self.btn_add_sheet.setObjectName("panelIconBtn")
        self.btn_add_sheet.setToolTip("添加图纸 (Ctrl+O)")
        self.btn_add_sheet.clicked.connect(self.open_drawing)
        hh.addWidget(self.btn_add_sheet)
        self.btn_del_sheet = QPushButton(_fluent("trash", "－"))
        self.btn_del_sheet.setObjectName("panelIconBtnDanger")
        self.btn_del_sheet.setToolTip("删除选中图纸")
        self.btn_del_sheet.clicked.connect(self._delete_sheet)
        hh.addWidget(self.btn_del_sheet)
        if T.icon_font_family():
            f = T.make_icon_font(14)
            if f:
                self.btn_add_sheet.setFont(f)
                self.btn_del_sheet.setFont(f)
        lv.addWidget(head)

        # 搜索框（bg-slate-50，placeholder「搜索图纸或图层」；隐藏非匹配行，row 索引不变）
        search_wrap = QWidget()
        sw = QVBoxLayout(search_wrap)
        sw.setContentsMargins(12, 8, 12, 4)
        sw.setSpacing(0)
        self.sheet_search = QLineEdit()
        self.sheet_search.setObjectName("sheetSearch")
        self.sheet_search.setPlaceholderText("搜索图纸或图层")
        self.sheet_search.setClearButtonEnabled(True)
        self.sheet_search.textChanged.connect(self._filter_sheets)
        sw.addWidget(self.sheet_search)
        lv.addWidget(search_wrap)

        self.sheet_list = QListWidget()
        self.sheet_list.setObjectName("sheetList")
        # P3：批量删除图纸支持 → 开启多选（Ctrl/Shift；空白处单击取消全选）
        from PySide6.QtWidgets import QAbstractItemView
        self.sheet_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.sheet_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sheet_list.customContextMenuRequested.connect(self._on_sheet_context_menu)
        lv.addWidget(self.sheet_list, 2)

        t_layers = QLabel("图层 / 块")
        t_layers.setObjectName("secTitle")
        lv.addWidget(t_layers)
        self.layer_tree = LayerTreeWidget()
        lv.addWidget(self.layer_tree, 1)

        # 底部收起按钮（原型「收起资源面板」）
        self.btn_collapse_left = QPushButton("收起资源面板")
        self.btn_collapse_left.setObjectName("collapseBtn")
        self.btn_collapse_left.clicked.connect(lambda: self._toggle_panel("left"))
        lv.addWidget(self.btn_collapse_left)

        left.setMinimumWidth(200)
        left.setMaximumWidth(320)
        left.setObjectName("panel")
        split_main.addWidget(left)
        self._left_panel = left

        # 中间：深色画布区（v3：工具条通栏置顶 / 选择状态浮左下 / 提示浮右下）
        wrap = QWidget()
        wrap.setObjectName("canvasWrap")
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        # 顶部工具条：通栏深色条（main.html 对齐，不再浮动）
        fb = QWidget()
        fb.setObjectName("floatBar")
        fh = QHBoxLayout(fb)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.setSpacing(0)
        self.canvas_toolbar = CanvasToolbar()
        fh.addWidget(self.canvas_toolbar)
        grid.addWidget(fb, 0, 0)

        self.canvas = CanvasView()
        self.canvas.setMinimumWidth(400)
        grid.addWidget(self.canvas, 1, 0)

        # 左下：选择状态浮层
        self.selection_bar = SelectionBar()
        self.selection_bar.setObjectName("selOverlay")
        grid.addWidget(self.selection_bar, 1, 0, Qt.AlignBottom | Qt.AlignLeft)

        # 右下：操作提示
        hint = QLabel("双击/框选实体 · 回车分配到当前 BOQ 行")
        hint.setObjectName("hintLabel")
        grid.addWidget(hint, 1, 0, Qt.AlignBottom | Qt.AlignRight)

        split_main.addWidget(wrap)

        # 右栏：图标 rail + 工作区页面（v3，main.html 对齐）
        # 结构：rail(52px 图标/短词按钮) + QTabWidget(原生 tabBar 隐藏)。
        # 工具条与 rail 解耦（各司其职）：rail 按钮 / Ctrl+1..6 切面板，工具条只管画布模式。
        right = QWidget()
        rv = QHBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self._build_right_rail())

        pages = QVBoxLayout()
        pages.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(pages, 1)

        self.boq_table = BoqTable()
        # P1-10：BOQ 搜索框（过滤行 + 命中高亮）
        self.boq_search = QLineEdit()
        self.boq_search.setPlaceholderText("搜索 BOQ：编号 / 描述 / 单位（输入即过滤）")
        self.boq_search.setClearButtonEnabled(True)
        self.boq_search.textChanged.connect(self.boq_table.set_filter)
        self.boq_page = QWidget()
        bv = QVBoxLayout(self.boq_page)
        bv.setContentsMargins(6, 6, 6, 0)
        bv.setSpacing(6)
        # 顶行：清单计数 + 「重新导入」（原型 main.html:100）
        bh = QHBoxLayout()
        bh.setSpacing(6)
        self.boq_count_label = QLabel("共 0 条清单项")
        self.boq_count_label.setStyleSheet(
            f"color:{T.TEXT_SECONDARY}; font-size:{T.FONT_SIZE_CAPTION}px;")
        bh.addWidget(self.boq_count_label)
        bh.addStretch(1)
        self.btn_boq_reimport = QPushButton("重新导入")
        self.btn_boq_reimport.setObjectName("linkBtn")
        self.btn_boq_reimport.setCursor(Qt.PointingHandCursor)
        self.btn_boq_reimport.setToolTip("从 Excel 重新导入 BOQ 清单（覆盖当前清单）")
        self.btn_boq_reimport.clicked.connect(self.import_boq)
        bh.addWidget(self.btn_boq_reimport)
        bv.addLayout(bh)
        bv.addWidget(self.boq_search)
        bv.addWidget(self.boq_table, 1)
        self.right_tabs = QTabWidget()
        self.right_tabs.setMovable(False)
        self.right_tabs.addTab(self.binding_workbench, "绑定工作台")
        self.right_tabs.addTab(self.boq_page, "BOQ 清单")
        self.right_tabs.addTab(self.mapping_panel, "计量")
        self.right_tabs.addTab(self.legend_panel, "图例标定")
        self.right_tabs.addTab(self.entity_properties, "实体属性")
        self.right_tabs.addTab(self.project_properties, "项目属性")
        self.right_tabs.addTab(self.history_panel, "操作记录")
        self.right_tabs.tabBar().hide()
        pages.addWidget(self.right_tabs)
        # rail 高亮同步（right_tabs 构建完成后再接线；工具条已解耦不参与）
        self.right_tabs.currentChanged.connect(self._on_right_tab_changed)
        self._rail_buttons[0].setChecked(True)
        right.setMinimumWidth(330)
        right.setObjectName("panel")
        split_main.addWidget(right)
        self._right_panel = right

        # 画布为英雄区：左栏固定(0)、画布主导(5)、右栏(2)
        split_main.setStretchFactor(0, 0)
        split_main.setStretchFactor(1, 5)
        split_main.setStretchFactor(2, 2)

        root.addWidget(split_main, 1)

        # 底部状态栏：常驻统计指标 + 消息 + LLM 状态
        self._stat_label = QLabel("实体 0 · 图层 0 · BOQ 0 · 模式 拾取")
        self._stat_label.setStyleSheet(f"color:{T.TEXT_SECONDARY}; padding-right:8px;")
        self.statusBar().addPermanentWidget(self._stat_label)
        # 当前 LLM 后端指示：可点击打开 LLM 设置（P0-2）
        self._llm_status_label = QPushButton("LLM: —")
        self._llm_status_label.setObjectName("llmStatusBtn")
        self._llm_status_label.setCursor(Qt.PointingHandCursor)
        self._llm_status_label.setToolTip("点击打开「LLM 设置」：切换后端 / 测速 / 配置 Fallback")
        self._llm_status_label.clicked.connect(self.open_llm_settings)
        self.statusBar().addPermanentWidget(self._llm_status_label)
        self._refresh_llm_status()
        # 操作历史（P0-7）：所有 statusBar 消息进入环形缓存，点按钮回看
        self.btn_history = QPushButton("🕘 记录")
        self.btn_history.setObjectName("llmStatusBtn")
        self.btn_history.setToolTip("查看最近操作记录")
        self.btn_history.clicked.connect(self._toggle_history)
        self.statusBar().addPermanentWidget(self.btn_history)
        self.statusBar().messageChanged.connect(self._on_status_message)
        self.statusBar().showMessage("就绪")
        self._build_toast()

    # ---------- Toast 浮层（v3 main.html：操作反馈右下弹出，2.6s 自动消失） ----------
    def _build_toast(self):
        self._toast = QLabel(self)
        self._toast.setObjectName("toastLabel")
        self._toast.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast.hide)

    def show_toast(self, text: str, kind: str = "info", duration_ms: int = 2600):
        """kind: info（深） / success（绿） / warning（琥珀）。"""
        if not text:
            return
        colors = {
            "success": (T.SUCCESS_BG, "#FFFFFF"),
            "warning": (T.WARNING_BAR_TEXT, "#FFFFFF"),
        }
        bg, fg = colors.get(kind, (T.OVERLAY_BG, T.OVERLAY_TEXT))
        self._toast.setStyleSheet(
            f"QLabel#toastLabel {{ background:{bg}; color:{fg}; border-radius:6px;"
            f" padding:8px 16px; font-size:{T.FONT_SIZE_BODY}px; }}")
        self._toast.setText(text)
        self._toast.adjustSize()
        m = 24
        x = self.width() - self._toast.width() - m
        y = self.height() - self.statusBar().height() - self._toast.height() - m
        self._toast.move(max(m, x), max(m, y))
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(duration_ms)

    @staticmethod
    def _toast_kind(text: str) -> str:
        """按消息语义定 Toast 颜色：失败→warning，完成/确认→success，其余→info。"""
        if ("失败" in text) or text.startswith("⚠") or "已忽略" in text or "请先" in text:
            return "warning"
        if text.startswith(("已确认", "已恢复")) or "完成" in text:
            return "success"
        return "info"

    def _build_topbar(self) -> QWidget:
        """v3 顶栏（main.html 1:1）：品牌块 / 项目 / 新建 / 打开 / AI 算量▾ / 导出 / 更多▾。"""
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setFixedHeight(T.TOPBAR_HEIGHT)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 6, 16, 6)
        h.setSpacing(8)

        def _icon(key: str) -> str:
            """Fluent 图标文本；无图标字体时回退空（按钮仍有文字）。"""
            if T.icon_font_family() is None:
                return ""
            return T.ICONS.get(key, "") + " "

        # ---- 品牌块：cyan 方块图标 + 双行标题，右侧分隔线 ----
        brand_icon = QLabel(T.ICONS.get("document", "图") if T.icon_font_family() else "图")
        brand_icon.setObjectName("brandIcon")
        brand_icon.setFixedSize(28, 28)
        brand_icon.setAlignment(Qt.AlignCenter)
        if T.icon_font_family():
            f = T.make_icon_font(17)
            if f:
                brand_icon.setFont(f)
        brand_icon.setToolTip("图纸算量 CAD·BOQ")
        h.addWidget(brand_icon)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        title = QLabel('图纸算量 <span style="color:#22D3EE">CAD·BOQ</span>')
        title.setObjectName("brandTitle")
        title.setTextFormat(Qt.RichText)
        sub = QLabel("电气工程数量智能核算")
        sub.setObjectName("brandSub")
        brand_col.addWidget(title)
        brand_col.addWidget(sub)
        h.addLayout(brand_col)

        div1 = QFrame()
        div1.setFrameShape(QFrame.VLine)
        div1.setStyleSheet(f"color: {T.TOPBAR_BORDER};")
        div1.setFixedHeight(20)
        h.addWidget(div1)
        h.addSpacing(4)

        # ---- 项目下拉（QComboBox 保留原生交互，样式对齐深色描边） ----
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(202)
        self.project_combo.setToolTip("切换项目（右键：重命名 / 删除）")
        h.addWidget(self.project_combo)

        self.btn_new_project = QPushButton(_icon("add") + "新建")
        self.btn_new_project.setObjectName("topBtn")
        self.btn_new_project.clicked.connect(self.new_project)
        h.addWidget(self.btn_new_project)

        self.btn_open = QPushButton(_icon("open") + "打开图纸")
        self.btn_open.setObjectName("topBtn")
        self.btn_open.clicked.connect(self.open_drawing)
        h.addWidget(self.btn_open)

        div2 = QFrame()
        div2.setFrameShape(QFrame.VLine)
        div2.setStyleSheet(f"color: {T.TOPBAR_BORDER};")
        div2.setFixedHeight(20)
        h.addWidget(div2)
        h.addSpacing(4)

        # ---- AI 算量 hero（cyan 实心 + 下拉三选项，原型 runAI 三入口） ----
        self.btn_ai = QPushButton(_icon("magic") + "AI 算量")
        self.btn_ai.setObjectName("heroBtn")
        ai_menu = QMenu(self)
        ai_menu.addAction("识别当前图纸", self.ai_takeoff_current)
        ai_menu.addAction("批量识别全部图纸", self.ai_takeoff_folder)
        ai_menu.addSeparator()
        ai_menu.addAction("从文件夹批量导入", self.import_folder_drawings)
        ai_menu.addSeparator()
        # 绑定候选流水线（v3 重设计删工具栏后必须在此提供入口，否则候选永远无法生成）
        self._more_actions["extract_objects"] = ai_menu.addAction(
            "提取工程对象", self.binding_workbench.extract_objects)
        self._more_actions["gen_candidates"] = ai_menu.addAction(
            "生成绑定候选", self.binding_workbench.run_generate)
        self._more_actions["llm_classify"] = ai_menu.addAction(
            "LLM 补充分类", self.binding_workbench.run_llm_classify)
        self.btn_ai.setMenu(ai_menu)
        h.addWidget(self.btn_ai)

        self.btn_export = QPushButton(_icon("export") + "导出")
        self.btn_export.setObjectName("topBtn")
        self.btn_export.clicked.connect(self.export_report)
        h.addWidget(self.btn_export)

        h.addStretch(1)

        # ---- 更多▾：低频工具 + 视图/过滤（原工具栏入口收拢于此） ----
        more_menu = QMenu(self)
        # _more_actions 已在 _build_ui 顶部初始化（AI 菜单先于此处使用）
        self._more_actions["import_boq"] = more_menu.addAction(
            "导入 BOQ", self.import_boq)
        self._more_actions["repair_boq"] = more_menu.addAction(
            "修复 BOQ", self.repair_boq)
        self._more_actions["export_layers"] = more_menu.addAction(
            "导出图层清单", self.export_layer_list)
        self._more_actions["materials"] = more_menu.addAction(
            "主要材料表", self.open_materials_dialog)
        more_menu.addSeparator()
        self._more_actions["legend"] = more_menu.addAction(
            "图例标定", self.focus_legend)
        self._more_actions["project_properties"] = more_menu.addAction(
            "项目属性…", self.focus_project_properties)
        self._more_actions["settings"] = more_menu.addAction(
            "项目设置…", self.open_project_settings)
        self._more_actions["llm"] = more_menu.addAction(
            "LLM 设置…", self.open_llm_settings)
        self._more_actions["db_maintenance"] = more_menu.addAction(
            "数据库瘦身 (VACUUM)…", self.open_db_maintenance)
        more_menu.addSeparator()
        # 视图 / 实体过滤：占位菜单，_build_ui 中 canvas_toolbar 建好后填充
        self._view_menu = more_menu.addMenu("视图")
        self._type_menu = more_menu.addMenu("实体类型过滤")

        btn_more = QPushButton("更多 " + T.ICONS.get("chevron", ""))
        btn_more.setObjectName("topBtn")
        btn_more.setMenu(more_menu)
        btn_more.setToolTip("低频工具 / 视图 / 实体过滤 / 设置")
        h.addWidget(btn_more)

        return bar

    def _build_right_rail(self) -> QWidget:
        """右栏图标 rail（v3）：绑定 / 清单 / 计量 / 属性 / 记录 5 项。

        通过模块级 RAIL_TAB_INDEX 显式映射到 right_tabs 页签索引（非一一对应）。
        图例标定 / 项目属性经「更多 ▾」菜单或 Ctrl+1..6 到达。
        """
        from PySide6.QtWidgets import QToolButton, QButtonGroup

        rail = QWidget()
        rail.setObjectName("railBar")
        rail.setFixedWidth(T.RIGHT_RAIL_W)
        v = QVBoxLayout(rail)
        v.setContentsMargins(4, 8, 4, 8)
        v.setSpacing(4)

        labels = ["绑定", "清单", "计量", "属性", "记录"]
        tips = ["绑定工作台：AI/规则候选审核", "BOQ 清单", "计量映射",
                "实体属性（当前选择）", "操作记录"]
        self._rail_group = QButtonGroup(self)
        self._rail_group.setExclusive(True)
        self._rail_buttons: list[QToolButton] = []
        for i, (text, tip) in enumerate(zip(labels, tips)):
            btn = QToolButton()
            btn.setObjectName("railBtn")
            btn.setText(text)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, idx=i: self.right_tabs.setCurrentIndex(RAIL_TAB_INDEX[idx]))
            self._rail_group.addButton(btn, i)
            self._rail_buttons.append(btn)
            v.addWidget(btn)
        v.addStretch(1)

        btn_help = QToolButton()
        btn_help.setObjectName("railBtn")
        btn_help.setText("帮助")
        btn_help.setToolTip("使用说明 (F1)")
        btn_help.setCursor(Qt.PointingHandCursor)
        btn_help.clicked.connect(self.show_help)
        v.addWidget(btn_help)

        return rail

    def _on_right_tab_changed(self, idx: int):
        """tab 切换的唯一汇合点：rail 高亮（工具条已解耦，不再镜像）。"""
        try:
            self._rail_buttons[RAIL_TAB_INDEX.index(idx)].setChecked(True)
        except ValueError:
            # 非 rail 面板（图例标定 / 项目属性）：清空 rail 高亮避免误导
            # （exclusive QButtonGroup 禁止直接取消勾选，先临时解除独占）
            self._rail_group.setExclusive(False)
            for btn in self._rail_buttons:
                btn.setChecked(False)
            self._rail_group.setExclusive(True)

    def _update_stats(self):
        """更新底部状态栏：项目 / 图纸 / 工作模式 / 统计信息"""
        self._refresh_status_breadcrumb()

    def _refresh_boq_count(self):
        """BOQ 页头行计数（原型「共 N 条清单项」）。"""
        if hasattr(self, "boq_count_label"):
            self.boq_count_label.setText(
                f"共 {getattr(self, '_stat_boq', 0)} 条清单项")

    # ---------- 状态消息中心（P0-7） ----------
    def _on_status_message(self, text: str):
        """statusBar 消息变时抓进环形缓存（自动覆盖所有 showMessage 调用点）。"""
        if not text:
            return
        entry = (time.time(), text)
        self._history.append(entry)
        if len(self._history) > 200:
            del self._history[:len(self._history) - 200]
        # v3：操作记录面板实时跟随（面板与状态栏同源）
        if hasattr(self, "history_panel"):
            self.history_panel.add_entry(*entry)

    def _toggle_history(self):
        """v3：状态栏「🕘 记录」→ 切到右栏操作记录面板（原浮层已升级为面板）。"""
        self._right_panel.setVisible(True)
        self.canvas_toolbar.btn_right.setChecked(True)
        self.right_tabs.setCurrentIndex(6)   # 6 = 操作记录

    def _build_menu(self):
        """v2：菜单栏已由顶部品牌栏替代（保留空实现以兼容外部调用）"""
        self.menuBar().hide()

    def _register_shortcuts(self):
        """注册全局快捷键：
        Ctrl+B 左栏 / Ctrl+Alt+B 右栏 / Ctrl+Z 撤销最近映射变更 (P0-8)。
        """
        sc_left = QShortcut(QKeySequence("Ctrl+B"), self)
        sc_left.activated.connect(lambda: self._toggle_panel("left"))
        sc_right = QShortcut(QKeySequence("Ctrl+Alt+B"), self)
        sc_right.activated.connect(lambda: self._toggle_panel("right"))
        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.activated.connect(self._undo_last)

        # P1-9 全套快捷键
        sc_new = QShortcut(QKeySequence("Ctrl+N"), self)
        sc_new.activated.connect(self.new_project)
        sc_open = QShortcut(QKeySequence("Ctrl+O"), self)
        sc_open.activated.connect(self.open_drawing)
        sc_export = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_export.activated.connect(self.export_report)
        sc_help = QShortcut(QKeySequence("F1"), self)
        sc_help.activated.connect(self.show_help)
        for i in range(1, 7):
            sc = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc.activated.connect(lambda _i=i: self._on_ctrl_tab_shortcut(_i))

    def _connect_signals(self):
        self.btn_new_project.clicked.connect(self.new_project)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        self.project_combo.setContextMenuPolicy(Qt.CustomContextMenu)  # P2：右键项目重命名/删除
        self.project_combo.customContextMenuRequested.connect(self._on_project_combo_context)
        self.sheet_list.currentRowChanged.connect(self._on_sheet_changed)

        self.canvas.entityPicked.connect(self._on_entity_picked)
        self.canvas.entitiesPicked.connect(self._on_entities_picked)

        self.layer_tree.layerVisibilityChanged.connect(self.canvas.set_layer_visible)
        self.layer_tree.layerAssociateRequested.connect(self._on_layer_associate)
        self.layer_tree.blockAssociateRequested.connect(self._on_block_associate)
        # Phase 2: Isolate / 锁定 / 颜色覆盖
        self.layer_tree.layerIsolateRequested.connect(self.canvas.isolate_layer)
        self.layer_tree.layersRestoreRequested.connect(self.canvas.restore_layers)
        self.layer_tree.layerLockRequested.connect(self._on_layer_lock)
        self.layer_tree.layerColorOverrideRequested.connect(self._on_layer_color_override)

        self.boq_table.itemSelected.connect(self._on_item_selected)
        self.boq_table.ruleChanged.connect(lambda iid, _r: self._recalc_and_refresh(iid))
        self.boq_table.scaleChanged.connect(lambda iid, _f: self._recalc_and_refresh(iid))

        self.mapping_panel.deleteMappingRequested.connect(self._on_delete_mapping)
        self.mapping_panel.recalcRequested.connect(lambda: self._recalc_and_refresh())

        # 图例标定面板
        self.legend_panel.locateRequested.connect(self._on_legend_locate)
        self.legend_panel.statusMessage.connect(self.statusBar().showMessage)

        # 绑定工作台
        self.binding_workbench.locateRequested.connect(self._on_binding_locate)
        self.binding_workbench.statusMessage.connect(self.statusBar().showMessage)
        self.binding_workbench.statusMessage.connect(
            lambda t: self.show_toast(t, self._toast_kind(t)))
        self.binding_workbench.bindingChanged.connect(self._recalc_and_refresh)
        self.binding_workbench.bindingChanged.connect(self._refresh_sheet_badges)
        # 绑定工作台内部 worker（生成候选/LLM 分类）经 busyChanged 汇入统一 busy 收口
        self.binding_workbench.busyChanged.connect(self._set_busy)

        # Phase 1 工具栏
        self.canvas_toolbar.modeChanged.connect(self._on_mode_changed)
        self.canvas_toolbar.contextModeChanged.connect(self._on_context_mode_changed)
        self.canvas_toolbar.zoomFitRequested.connect(self.canvas.zoom_fit)
        self.canvas_toolbar.zoomActualRequested.connect(self.canvas.zoom_actual)
        self.canvas_toolbar.zoomBackRequested.connect(self.canvas.zoom_back)
        self.canvas_toolbar.zoomForwardRequested.connect(self.canvas.zoom_forward)
        # 原型 zoom(±10)：每步 ×1.15；读数由画布 scaleChanged 回推（滚轮同样生效）
        self.canvas_toolbar.zoomInRequested.connect(
            lambda: self.canvas.zoom_step(1.15))
        self.canvas_toolbar.zoomOutRequested.connect(
            lambda: self.canvas.zoom_step(1 / 1.15))
        self.canvas.scaleChanged.connect(self.canvas_toolbar.set_zoom_pct)
        self.canvas_toolbar.set_zoom_pct(self.canvas.current_scale())
        self.canvas_toolbar.themeToggleRequested.connect(self._on_theme_toggle)
        self.canvas_toolbar.fullscreenToggleRequested.connect(self._toggle_fullscreen)
        self.canvas_toolbar.entityTypeVisibilityChanged.connect(self.canvas.set_type_visible)

        # 顶栏「更多 ▾」占位菜单回填：视图 / 实体类型过滤（_build_topbar 时工具栏未建）
        if getattr(self, "_view_menu", None) is not None:
            vm = self._view_menu
            vm.addAction(self.canvas_toolbar.btn_theme)
            vm.addAction(self.canvas_toolbar.btn_full)
            vm.addSeparator()
            vm.addAction(self.canvas_toolbar.btn_left)
            vm.addAction(self.canvas_toolbar.btn_right)
        if getattr(self, "_type_menu", None) is not None:
            for act in self.canvas_toolbar.type_actions.values():
                self._type_menu.addAction(act)
        # 快捷键：Ctrl+0 整图（Ctrl+1=100% 已由 _on_ctrl_tab_shortcut 在画布聚焦时承接）
        act_fit = QAction("整图", self)
        act_fit.setShortcut(QKeySequence("Ctrl+0"))
        act_fit.triggered.connect(self.canvas.zoom_fit)
        self.addAction(act_fit)
        # 初始化同步：工具栏默认关闭 TEXT/HATCH，画布需一致（否则"杂线/文字"全显示）
        for t in ("HATCH", "TEXT", "MTEXT"):
            self.canvas.set_type_visible(t, False)

        # v2：左右栏折叠
        self.canvas_toolbar.leftPanelToggleRequested.connect(lambda: self._toggle_panel("left"))
        self.canvas_toolbar.rightPanelToggleRequested.connect(lambda: self._toggle_panel("right"))

        # Phase 3 选择状态条
        self.selection_bar.assignRequested.connect(self._commit_pending)
        self.selection_bar.clearRequested.connect(self._clear_pending)
        # v3 实体属性面板：分配入口与选择条同一落点
        self.entity_properties.assignRequested.connect(self._commit_pending)

    # ---------- 模式 / 主题 / 全屏 / 设置 ----------
    def _on_mode_changed(self, mode: str):
        self._mode = mode
        self._update_stats()
        self.statusBar().showMessage(f"模式已切换：{mode}（{ {'pick':'双击或框选实体待分配','layer':'在图层树右键批量关联','block':'在块树右键批量关联（计数规则）'}.get(mode,'') }）")

    def _on_context_mode_changed(self, mode: str):
        # 工具条模式只改画布工作上下文（v3 原型语义），不再镜像切换右栏面板
        self._refresh_status_breadcrumb()

    def _refresh_status_breadcrumb(self):
        """底部状态栏（main.html 1:1）：实体 N · 图层 N · BOQ N · 模式 X"""
        mode_labels = {
            "browse": "清单", "mapping": "计量", "legend": "图例",
            "ai": "绑定", "props": "属性", "pick": "拾取",
        }
        mode = mode_labels.get(
            getattr(self.canvas_toolbar, "_context_mode", "browse"), "清单")
        self._stat_label.setText(
            f"实体 {getattr(self, '_stat_entities', 0):,} · "
            f"图层 {getattr(self, '_stat_layers', 0):,} · "
            f"BOQ {getattr(self, '_stat_boq', 0):,} · 模式 {mode}")

    def _on_theme_toggle(self):
        self._dark = self.canvas_toolbar.btn_theme.isChecked()
        self.canvas.set_theme(self._dark)
        self._save_settings()

    def _on_ctrl_tab_shortcut(self, idx: int):
        """Ctrl+1..5：焦点在画布时保留 Ctrl+1=100% 缩放（P1-14 语义对齐），否则切标签页。"""
        if idx == 1 and self.canvas.hasFocus():
            self.canvas.zoom_actual()
            return
        self._focus_right_tab(idx)

    def _focus_right_tab(self, idx: int):
        """Ctrl+1..5 切换到右侧工作区对应标签页。"""
        if 1 <= idx <= self.right_tabs.count():
            self.right_tabs.setCurrentIndex(idx - 1)

    def _toggle_panel(self, which: str):
        """v2 左右栏折叠：隐藏后面板让画布独占空间"""
        if which == "left":
            vis = not self._left_panel.isVisible()
            self._left_panel.setVisible(vis)
            self.canvas_toolbar.btn_left.setChecked(vis)
            self.statusBar().showMessage("左侧面板" + ("已显示" if vis else "已隐藏"))
        else:
            vis = not self._right_panel.isVisible()
            self._right_panel.setVisible(vis)
            self.canvas_toolbar.btn_right.setChecked(vis)
            self.statusBar().showMessage("右侧面板" + ("已显示" if vis else "已隐藏"))

    def _toggle_fullscreen(self):
        if self._fullscreen:
            # 退出全屏：恢复
            self._left_panel.show()
            self._right_panel.show()
            self.canvas_toolbar.show()
            self._fullscreen = False
            self.canvas_toolbar.btn_full.setText("⛶ 全屏")
        else:
            # 进入全屏：仅留画布
            self._left_panel.hide()
            self._right_panel.hide()
            self.canvas_toolbar.show()
            self._fullscreen = True
            self.canvas_toolbar.btn_full.setText("⛶ 退出")
        self.statusBar().showMessage(
            "进入全屏" if self._fullscreen else "退出全屏")

    def _settings(self) -> QSettings:
        return QSettings("CADBOQ", "Tool")

    def _save_settings(self):
        s = self._settings()
        save_window_state(s, self, self._split_main if hasattr(self, "_split_main") else None)

    def _restore_settings(self):
        s = self._settings()
        restore_window_state(s, self, self._split_main if hasattr(self, "_split_main") else None)
        # 恢复最近项目
        pid = s.value("recent_project_id", type=int)
        if pid:
            idx = self.project_combo.findData(pid)
            if idx >= 0:
                self.project_combo.setCurrentIndex(idx)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self._toggle_fullscreen()
            event.accept()
            return
        # Phase 3: Enter 提交待选
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.canvas.get_pending():
            self._commit_pending()
            event.accept()
            return
        # Phase 3: Esc 清空待选
        if event.key() == Qt.Key_Escape and self.canvas.get_pending():
            self._clear_pending()
            self.statusBar().showMessage("已清空待选")
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    # ---------- 项目 ----------
    def _reload_projects(self):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for p in db.list_projects():
            self.project_combo.addItem(p.name, p.id)
        self.project_combo.blockSignals(False)
        if self.project_combo.count():
            self._project_id = self.project_combo.currentData()
            self._reload_sheets()
            self._refresh_base_layers()
        else:
            self._project_id = None
        self._refresh_enabled()

    def _set_busy(self, busy: bool):
        """统一 busy 收口（P0 C1 修复）：后台任务运行期间禁用易冲突入口。

        所有 worker 的启动/结束回调都经此置位：True 时按钮置灰防止
        并发触发多个 QThread 造成数据竞争；任务结束自动恢复。
        """
        self._busy = busy
        self._refresh_enabled()

    def _refresh_enabled(self):
        """上下文统一启用态：全部→无项目→项目级按钮禁用；有图纸→图纸级按钮禁用。

        P1-12 的单一真相源：所有主窗口按钮/菜单动作都从这里取 enable 状态，
        避免各自散落判断。busy=True 时（后台任务运行中）一并禁用相关入口。
        """
        has_proj = self._project_id is not None
        proj_ready = has_proj and not getattr(self, "_busy", False)
        # 项目级
        if hasattr(self, "btn_open"):
            self.btn_open.setEnabled(proj_ready)
        if hasattr(self, "btn_ai"):
            self.btn_ai.setEnabled(proj_ready)
        if hasattr(self, "btn_add_sheet"):
            self.btn_add_sheet.setEnabled(proj_ready)
        if hasattr(self, "btn_boq_reimport"):
            self.btn_boq_reimport.setEnabled(proj_ready)
        for key in ("import_boq", "repair_boq", "export_layers",
                    "materials", "legend", "project_properties", "settings",
                    "extract_objects", "gen_candidates", "llm_classify"):
            act = getattr(self, "_more_actions", {}).get(key)
            if act is not None:
                act.setEnabled(proj_ready)
        # 图纸级（导出需当前图纸；busy 时一并禁用，防并发导出）
        has_sheet = has_proj and self._sheet_id is not None
        if hasattr(self, "btn_export"):
            self.btn_export.setEnabled(has_sheet and not self._busy)
        # 删除图纸需有选中项（P3：多选≥1 即可）
        has_sel = has_sheet and len(self.sheet_list.selectedItems()) > 0
        if hasattr(self, "btn_del_sheet"):
            self.btn_del_sheet.setEnabled(has_proj and has_sel)
        # P1-12 各工作区面板按钮与上下文对齐
        if hasattr(self, "binding_workbench"):
            self.binding_workbench.refresh_enabled(has_proj)
        if hasattr(self, "project_properties") and hasattr(self.project_properties, "refresh_enabled"):
            self.project_properties.refresh_enabled(has_proj)
        if hasattr(self, "legend_panel") and hasattr(self.legend_panel, "refresh_enabled"):
            self.legend_panel.refresh_enabled(has_proj)
        if hasattr(self, "mapping_panel") and hasattr(self.mapping_panel, "refresh_enabled"):
            self.mapping_panel.refresh_enabled(has_proj)

    def new_project(self):
        """新建项目：输入名称即创建（不再用另存为对话框，项目存于本地 DB）。"""
        import datetime
        suggested = f"项目 {datetime.datetime.now():%Y%m%d %H%M}"
        name, ok = QInputDialog.getText(
            self, "新建项目", "输入项目名称：", text=suggested)
        if not ok or not (name or "").strip():
            return
        name = name.strip()
        # 同名提示（DB 不禁止重名，提示避免误建多个）
        exists = [p for p in db.list_projects() if p.name == name]
        if exists:
            ret = QMessageBox.question(
                self, "项目已存在",
                f"已存在名为「{name}」的项目，仍要创建吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        pid = db.create_project(name)
        self._reload_projects()
        idx = self.project_combo.findData(pid)
        if idx >= 0:
            self.project_combo.setCurrentIndex(idx)
        self.statusBar().showMessage(f"已创建项目：{name}")

    def _on_project_changed(self, _idx):
        self._project_id = self.project_combo.currentData()
        self._current_item_id = None
        self._sheet_id = None
        self._reload_sheets()
        self._refresh_base_layers()
        self.legend_panel.load_project(self._project_id)
        self.binding_workbench.load_project(self._project_id)
        self.project_properties.load_project(self._project_id)
        # 项目切换后重算 BOQ / 实体计数（状态栏与 BOQ 页头行共用）
        self._stat_boq = len(db.get_boq_items(self._project_id)) if self._project_id else 0
        self._refresh_boq_count()
        self._refresh_status_breadcrumb()
        self._refresh_enabled()

    # ---------- P2：项目重命名 / 删除（顶栏项目下拉右键菜单） ----------
    def _on_project_combo_context(self, pos):
        """项目下拉框右键菜单：重命名 / 删除当前项目。"""
        menu = QMenu(self)
        act_rename = menu.addAction("重命名当前项目…", self.rename_project)
        act_delete = menu.addAction("删除当前项目…", self.delete_project)
        act_rename.setEnabled(self._project_id is not None)
        act_delete.setEnabled(self._project_id is not None)
        menu.exec(self.project_combo.mapToGlobal(pos))

    def rename_project(self):
        """重命名当前项目：输入新名称。"""
        if self._project_id is None:
            return
        p = db.get_project(self._project_id)
        if p is None:
            return
        name, ok = QInputDialog.getText(
            self, "重命名项目", "输入新的项目名称：", text=p.name)
        if not ok or not (name or "").strip():
            return
        name = name.strip()
        db.rename_project(self._project_id, name)
        self._reload_projects()
        self.statusBar().showMessage(f"已重命名项目为：{name}")

    def delete_project(self):
        """删除当前项目：强确认（含全部图纸/实体/映射，不可恢复）。"""
        if self._project_id is None:
            return
        p = db.get_project(self._project_id)
        if p is None:
            return
        name = p.name
        # 强确认：先选「是，删除」再输名字，防误触
        ret = QMessageBox.warning(
            self, "删除项目",
            f"确定删除项目「{name}」？\n\n"
            "将同时删除该项目下的全部图纸、实体、BOQ 清单、映射与设定，且不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        verify, ok2 = QInputDialog.getText(
            self, "确认删除",
            f"此操作不可撤销。请输入项目名称「{name}」以确认：")
        if not ok2 or verify.strip() != name:
            self.statusBar().showMessage("取消删除：输入的项目名称不匹配")
            return
        db.delete_project(self._project_id)
        self._project_id = None
        self._reload_projects()
        self.statusBar().showMessage(f"已删除项目：{name}")

    @staticmethod
    def _sheet_status_visual(st) -> tuple[str, str, str]:
        """图纸状态 → (状态文本, 文字色, 状态点色)。

        原型：cyan-500 已识别 / amber-400 待复核 / slate-300 未执行 AI。
        """
        if st is None:
            return ("未执行 AI", T.TEXT_DISABLED, "#CBD5E1")
        if st["pending"]:
            return (f"待复核 {st['pending']}", T.WARNING_BAR_TEXT, "#FBBF24")
        if st["accepted"]:
            return (f"已确认 {st['accepted']}", T.SUCCESS_BG, "#06B6D4")
        return ("已提取", T.ACCENT_LINK, "#06B6D4")

    def _reload_sheets(self):
        self.sheet_list.clear()
        self._sheet_badge_labels = {}
        self._sheet_dot_labels = {}
        if self._project_id is None:
            return
        base = db.get_base_sheet(self._project_id)
        base_id = base.id if base else None
        stats = db.sheet_candidate_stats(self._project_id)
        fm = self.sheet_list.fontMetrics()
        for s in db.get_sheets(self._project_id):
            prefix = "[底图] " if s.id == base_id else ""
            item = QListWidgetItem()
            item.setData(Qt.UserRole, s.id)
            item.setData(Qt.UserRole + 1, s.filename)   # 搜索/面包屑用
            tip = f"{prefix}{s.filename} · {s.entity_count:,} 实体"
            st = stats.get(s.id)
            if st is not None:
                tip += (f" · 工程对象 {st['objects']} · 待复核 {st['pending']}"
                        f" · 已确认 {st['accepted']}")
            item.setToolTip(tip)
            self.sheet_list.addItem(item)

            # 卡片行（原型 1:1）：行1 = 状态点 + 文件名 + 右侧实体数；行2 = 状态 caption
            row = QWidget()
            v = QVBoxLayout(row)
            v.setContentsMargins(10, 6, 10, 6)
            v.setSpacing(2)
            l1 = QHBoxLayout()
            l1.setSpacing(6)
            st_text, st_fg, dot_hex = self._sheet_status_visual(st)
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background:{dot_hex}; border-radius:4px;")
            l1.addWidget(dot)
            name = QLabel(prefix + fm.elidedText(
                s.filename, Qt.ElideMiddle, 160))
            name.setStyleSheet(f"color:{T.TEXT_PRIMARY};")
            l1.addWidget(name, 1)
            count = QLabel(f"{s.entity_count:,}")
            count.setStyleSheet(
                f"color:{T.TEXT_DISABLED}; font-size:{T.FONT_SIZE_CAPTION}px;")
            l1.addWidget(count)
            v.addLayout(l1)
            caption = QLabel(st_text)
            caption.setStyleSheet(
                f"color:{st_fg}; font-size:{T.FONT_SIZE_CAPTION}px;"
                f" padding-left:14px;")
            v.addWidget(caption)
            item.setSizeHint(row.sizeHint())
            self.sheet_list.setItemWidget(item, row)
            self._sheet_badge_labels[s.id] = caption
            self._sheet_dot_labels[s.id] = dot
        self._filter_sheets(self.sheet_search.text())

    def _filter_sheets(self, text: str):
        """图纸搜索：隐藏非匹配行（row 索引不变，_on_sheet_changed 映射仍成立）。"""
        kw = (text or "").strip().lower()
        for i in range(self.sheet_list.count()):
            it = self.sheet_list.item(i)
            name = it.data(Qt.UserRole + 1) or ""
            it.setHidden(bool(kw) and kw not in name.lower())

    def _refresh_sheet_badges(self):
        """绑定状态变化后仅刷新状态 caption + 圆点（不重建列表，保持选中与滚动位置）。"""
        if self._project_id is None or not hasattr(self, "_sheet_badge_labels"):
            return
        stats = db.sheet_candidate_stats(self._project_id)
        dots = getattr(self, "_sheet_dot_labels", {})
        for sid, caption in self._sheet_badge_labels.items():
            st_text, st_fg, dot_hex = self._sheet_status_visual(stats.get(sid))
            caption.setText(st_text)
            caption.setStyleSheet(
                f"color:{st_fg}; font-size:{T.FONT_SIZE_CAPTION}px;"
                f" padding-left:14px;")
            dot = dots.get(sid)
            if dot is not None:
                dot.setStyleSheet(f"background:{dot_hex}; border-radius:4px;")

    def _delete_sheet(self):
        """删除所选图纸（支持批量）：一次弹窗确认，不再要求输入图纸名。

        P3：多选删除 —— 用 selectedItems() 取全部选中项；单张与多张共用
        弹窗确认（多张时文案提示数量），确定性动作保持一致。
        """
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        items = self.sheet_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先在图纸列表中选择要删除的图纸")
            return
        sheets = {s.id: s for s in db.get_sheets(self._project_id)}
        sids = [it.data(Qt.UserRole) for it in items if it.data(Qt.UserRole) in sheets]
        if not sids:
            return
        names = [sheets[sid].filename for sid in sids]
        n = len(sids)
        label = "、".join(names[:3]) + (f" 等 {n} 张" if n > 3 else "")
        # 单张/多张同一弹窗确认（去掉 P2 的输名二次确认）
        if n == 1:
            msg = (f"确定删除图纸「{names[0]}」？\n\n"
                   "将同时删除该图纸的全部实体、工程对象与 BOQ 映射，且不可恢复。")
        else:
            msg = (f"确定删除选中的 {n} 张图纸？\n\n"
                   f"{label}\n\n"
                   "将同时删除各图纸的全部实体、工程对象与 BOQ 映射，且不可恢复。")
        ret = QMessageBox.warning(
            self, "删除图纸", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        db.delete_sheets(sids)
        if self._sheet_id in sids:
            self._sheet_id = None
            self._current_blocks = {}
            self.canvas.build([], {})
            self.layer_tree.rebuild([], [])
            self._clear_pending()
            self._stat_entities = 0
            self._stat_layers = 0
            self._update_stats()
        self._reload_sheets()
        if self._project_id is not None:
            self._refresh_base_layers()
            # 保持当前图纸过滤（删除的是当前图纸时 self._sheet_id 已回落 None）
            self.legend_panel.set_sheet_filter(self._sheet_id)
            self.binding_workbench.load_project(self._project_id)
        self._refresh_enabled()
        self.statusBar().showMessage(f"已删除 {n} 张图纸：{label}")

    def _on_sheet_context_menu(self, pos):
        """图纸列表右键菜单：重新解析 / 批量重解析 / 设为/取消建筑底图"""
        if self._project_id is None:
            return
        item = self.sheet_list.itemAt(pos)
        menu = QMenu(self)
        if item is None:
            # 空白处右键：仅批量操作
            menu.addAction("重新解析全部图纸", self._batch_reparse_all)
            menu.exec(self.sheet_list.viewport().mapToGlobal(pos))
            return
        sid = item.data(Qt.UserRole)
        base = db.get_base_sheet(self._project_id)
        is_base = base is not None and base.id == sid
        menu.addAction("重新解析块定义", lambda: self._reparse_sheet(sid))
        menu.addAction("重新解析全部图纸", self._batch_reparse_all)
        menu.addSeparator()
        n_sel = len(self.sheet_list.selectedItems())
        if n_sel > 0:
            menu.addAction(f"删除所选图纸（{n_sel} 张）", self._delete_sheet)
            menu.addSeparator()
        if is_base:
            menu.addAction("取消建筑底图", self._clear_base_sheet)
        else:
            menu.addAction("设为建筑底图", lambda: self._set_base_sheet(sid))
        menu.exec(self.sheet_list.viewport().mapToGlobal(pos))

    def _set_base_sheet(self, sid: int):
        """设定某图纸为建筑底图，自动提取图层集并刷新画布/图例。"""
        name = ""
        for i in range(self.sheet_list.count()):
            it = self.sheet_list.item(i)
            if it.data(Qt.UserRole) == sid:
                name = it.text()
                break
        ret = QMessageBox.question(
            self, "设为建筑底图",
            f"将图纸「{name}」设为建筑底图？\n\n"
            "设定后：打开机电图纸时，与底图同名的图层以灰色斜体标识（保持可见，不隐藏），\n"
            "图例标定面板在「运算设备块」时自动过滤底图图层上的块。layer 0 和空名不参与减法。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret != QMessageBox.Yes:
            return
        db.set_base_sheet(self._project_id, sid)
        self._reload_sheets()
        self._refresh_base_layers()
        self.statusBar().showMessage(f"已设为建筑底图：{name}")

    def _clear_base_sheet(self):
        """取消建筑底图标记，恢复全部图层显示。"""
        db.clear_base_sheet(self._project_id)
        self._reload_sheets()
        self._refresh_base_layers()
        self.statusBar().showMessage("已取消建筑底图")

    def _reparse_sheet(self, sid: int):
        """重新解析已有图纸的块定义（修复嵌套块等解析增强后生效）。"""
        sheets = db.get_sheets(self._project_id)
        sheet = next((s for s in sheets if s.id == sid), None)
        if sheet is None:
            return
        # 源文件优先（DWG 直读优先）；源丢失才回退旧的转换产物 DXF
        path = sheet.src_path
        if not path or not os.path.isfile(path):
            path = sheet.dxf_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "重新解析",
                f"找不到源文件：\n{sheet.src_path}\n\n请确认文件未被移动或删除。")
            return
        if getattr(self, "_parse_worker", None) is not None and self._parse_worker.isRunning():
            QMessageBox.information(self, "提示", "已有图纸正在解析，请稍候")
            return

        self._reparse_sid = sid
        self._parse_src = path
        self.statusBar().showMessage("正在重新解析块定义…（大图可能需要 30-60 秒）")

        self._parse_worker = ParseWorker(path, cancel_event=self._make_parse_dialog("重新解析"))
        self._parse_worker.progress.connect(self._on_parse_progress)
        self._parse_worker.done.connect(self._on_parse_done)
        self._parse_worker.failed.connect(self._on_parse_failed)
        self._set_busy(True)
        self._parse_worker.start()

    def _make_parse_dialog(self, title: str) -> "object":
        """创建可取消的解析进度对话框并返回 cancel_event（P0-4）。"""
        import threading as _threading
        self._parse_cancel_event = _threading.Event()
        dlg = QProgressDialog("正在解析…", "取消", 0, 0, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(self._on_parse_cancel)
        dlg.show()
        self._parse_dialog = dlg
        return self._parse_cancel_event

    def _on_parse_cancel(self):
        """解析进度「取消」→ 设置协作停止事件（当前解析在最接近的进度点中止）。"""
        if getattr(self, "_parse_cancel_event", None) is not None:
            self._parse_cancel_event.set()
        if getattr(self, "_parse_dialog", None) is not None:
            self._parse_dialog.setLabelText("正在取消…")
        # 取消解析可能不触发 done/failed（worker 静默退出），这里立即放行入口
        self._set_busy(False)

    # ---------- 批量重新解析 ----------
    _STATUS_LABEL = {"convert": "转换中", "parse": "解析中", "db": "入库",
                     "ok": "完成", "error": "失败", "missing": "源文件缺失"}

    def _batch_reparse_all(self):
        """重新解析项目下全部图纸：三阶段并行流水线（转换池+解析进程池）。"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        if getattr(self, "_parse_worker", None) is not None and self._parse_worker.isRunning():
            QMessageBox.information(self, "提示", "已有图纸正在解析，请稍候")
            return
        if getattr(self, "_batch_reparse_worker", None) is not None and \
                self._batch_reparse_worker.isRunning():
            QMessageBox.information(self, "提示", "批量重新解析正在进行中")
            return
        sheets = db.get_sheets(self._project_id)
        if not sheets:
            QMessageBox.information(self, "提示", "当前项目没有图纸")
            return
        ret = QMessageBox.question(
            self, "批量重新解析",
            f"将重新解析项目下全部 {len(sheets)} 张图纸（应用嵌套块修复等解析增强）。\n\n"
            "· 多进程并行解析，约需数分钟\n"
            "· 解析完成后自动更新块定义与实体数据\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret != QMessageBox.Yes:
            return

        import threading
        self._batch_cancel = threading.Event()
        self._batch_reparse_worker = _BatchReparseWorker(
            self._project_id, self._batch_cancel)
        self._batch_reparse_worker.progress.connect(self._on_batch_reparse_progress)
        self._batch_reparse_worker.finished_ok.connect(self._on_batch_reparse_done)
        self._batch_reparse_worker.failed.connect(self._on_batch_reparse_failed)

        dlg = QProgressDialog("准备批量重新解析…", "取消", 0, len(sheets), self)
        dlg.setWindowTitle("批量重新解析")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(self._on_batch_reparse_cancel)
        self._batch_reparse_dlg = dlg
        dlg.show()
        self._set_busy(True)
        self._batch_reparse_worker.start()

    def _on_batch_reparse_cancel(self):
        """进度对话框「取消」→ 协作停止（当前文件跑完后停止）。"""
        if getattr(self, "_batch_cancel", None) is not None:
            self._batch_cancel.set()
        if getattr(self, "_batch_reparse_dlg", None) is not None:
            self._batch_reparse_dlg.setLabelText("正在停止…（等待当前文件完成）")

    def _on_batch_reparse_progress(self, done: int, total: int, filename: str, status: str):
        dlg = getattr(self, "_batch_reparse_dlg", None)
        label = self._STATUS_LABEL.get(status, status)
        if dlg is not None:
            dlg.setMaximum(total)
            dlg.setValue(done)
            if status == "convert":
                dlg.setLabelText(f"阶段1/3 · ODA 批量转换：{filename}")
            elif status in ("ok", "error", "missing"):
                dlg.setLabelText(f"{done}/{total} · {filename} — {label}")
            else:
                dlg.setLabelText(f"{done}/{total} · {filename} — {label}…")
        self.statusBar().showMessage(f"批量重解析 {done}/{total} · {filename} {label}")

    def _on_batch_reparse_done(self, stats: dict):
        self._set_busy(False)
        dlg = getattr(self, "_batch_reparse_dlg", None)
        if dlg is not None:
            dlg.reset()
            dlg.close()
            self._batch_reparse_dlg = None
        # 刷新图纸列表（实体数/块定义已更新）+ 底图图层联动 + 重载当前图纸视图
        self._reload_sheets()
        self._refresh_base_layers()
        if self._sheet_id is not None:
            cur = self.sheet_list.currentRow()
            if cur >= 0:
                self._on_sheet_changed(cur)
            self.legend_panel.set_sheet_filter(self._sheet_id)
        mins = stats.get("elapsed", 0) / 60
        msg = (f"批量重解析完成：{stats.get('ok', 0)}/{stats.get('total', 0)} 成功"
               f"（{mins:.1f} 分钟）")
        if stats.get("cancelled"):
            msg += " · 已取消"
        errors = stats.get("errors") or []
        self.statusBar().showMessage(msg)
        if errors:
            detail = "\n".join(errors[:20]) + ("\n…" if len(errors) > 20 else "")
            QMessageBox.warning(self, "批量重新解析", f"{msg}\n\n失败 {len(errors)} 张：\n{detail}")
        else:
            QMessageBox.information(self, "批量重新解析", msg)

    def _on_batch_reparse_failed(self, err: str):
        self._set_busy(False)
        dlg = getattr(self, "_batch_reparse_dlg", None)
        if dlg is not None:
            dlg.close()
            self._batch_reparse_dlg = None
        self._error_box(
            "批量重新解析", "批量重新解析异常终止。\n\n"
            "请检查：\n· 图纸文件是否被占用/移动\n· ODA 转换器配置是否正常\n"
            "· 磁盘空间是否充足\n\n（点击「显示详情」查看完整报错）", err)
        self._reload_sheets()

    def _refresh_base_layers(self):
        """提取底图图层集 → 同步到图层树和图例面板。"""
        base_layers = db.get_base_layers(self._project_id) if self._project_id else set()
        self.layer_tree.set_base_layers(base_layers)
        self.legend_panel.set_base_layers(base_layers)

    # ---------- 图纸 ----------
    def open_drawing(self):
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先新建项目")
            return
        if getattr(self, "_parse_worker", None) is not None and self._parse_worker.isRunning():
            QMessageBox.information(self, "提示", "已有图纸正在解析，请稍候")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开图纸", "", "CAD 文件 (*.dwg *.dxf)")
        if not path:
            return

        self._parse_src = path
        self.statusBar().showMessage("正在解析图纸…（大图可能需要 30-60 秒）")

        # 后台线程解析，避免 UI 冻结；对话框带「取消」（P0-4）
        self._parse_worker = ParseWorker(path, cancel_event=self._make_parse_dialog("图纸解析"))
        self._parse_worker.progress.connect(self._on_parse_progress)
        self._parse_worker.done.connect(self._on_parse_done)
        self._parse_worker.failed.connect(self._on_parse_failed)
        self._set_busy(True)
        self._parse_worker.start()

    def _on_parse_progress(self, done: int, total: int):
        dlg = getattr(self, "_parse_dialog", None)
        if dlg is None:
            return
        if done == -1:
            dlg.setRange(0, 0)
            dlg.setLabelText(f"正在收集块定义（{total} 个块）…")
            return
        if done == 0 and total > 0:
            dlg.setRange(0, total)
        if total > 0:
            dlg.setValue(min(done, total))
            dlg.setLabelText(f"正在解析实体 {done:,} / {total:,}…")

    def import_folder_drawings(self):
        """批量导入图纸文件夹（递归子目录）→ 解析缓存 + 入库"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先新建项目")
            return
        folder = QFileDialog.getExistingDirectory(
            self, "选择图纸文件夹（自动包含所有子文件夹的 DWG/DXF）", "")
        if not folder:
            return
        import threading as _threading
        self._import_cancel_event = _threading.Event()
        self._import_worker = _ImportFolderWorker(
            self._project_id, folder, cancel_event=self._import_cancel_event)
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.finished_ok.connect(self._on_import_done)
        self._import_worker.failed.connect(self._on_import_failed)
        self._import_dialog = QProgressDialog("扫描图纸中…", "取消", 0, 0, self)
        self._import_dialog.setWindowTitle("批量导入图纸")
        self._import_dialog.setWindowModality(Qt.WindowModal)
        self._import_dialog.setAutoClose(False)
        self._import_dialog.setAutoReset(False)
        self._import_dialog.canceled.connect(self._on_import_cancel)
        self._import_dialog.show()
        self._set_busy(True)
        self._import_worker.start()

    def _on_import_cancel(self):
        """批量导入「取消」→ 协作停止（当前文件完成后停止）。"""
        if getattr(self, "_import_cancel_event", None) is not None:
            self._import_cancel_event.set()
        if getattr(self, "_import_dialog", None) is not None:
            self._import_dialog.setLabelText("正在停止…（等待当前文件完成）")

    def _on_import_progress(self, done: int, total: int, name: str, status: str):
        dlg = getattr(self, "_import_dialog", None)
        if dlg is None:
            return
        dlg.setRange(0, max(total, 1))
        dlg.setValue(min(done, max(total, 1)))
        flag = {"ok": "✓", "error": "✗", "skip": "—"}.get(status, "")
        dlg.setLabelText(f"[{done}/{total}] {flag} {name}")

    def _on_import_done(self, stats: dict):
        self._set_busy(False)
        dlg = getattr(self, "_import_dialog", None)
        if dlg:
            dlg.close()
            self._import_dialog = None
        self._reload_sheets()
        self.binding_workbench.load_project(self._project_id)
        msg = f"批量导入完成：成功 {stats['imported']} / 跳过 {stats['skipped']} / 失败 {len(stats['errors'])}"
        if stats["errors"]:
            msg += "\n\n失败：" + "\n".join(stats["errors"][:8])
        self.statusBar().showMessage(msg.splitlines()[0])
        QMessageBox.information(self, "批量导入", msg)

    def _on_import_failed(self, err: str):
        self._set_busy(False)
        dlg = getattr(self, "_import_dialog", None)
        if dlg:
            dlg.close()
            self._import_dialog = None
        self._error_box(
            "批量导入失败", "批量导入未能完成。\n\n"
            "请检查：\n· 文件夹路径是否可读\n· 是否包含损坏/加密的图纸\n"
            "· 磁盘空间是否充足", err[:2000])

    def _on_parse_done(self, dxf_path: str, drawing):
        self._set_busy(False)
        dlg = getattr(self, "_parse_dialog", None)
        if dlg is not None:
            dlg.close()
            self._parse_dialog = None

        blocks_json = json.dumps(drawing.blocks, ensure_ascii=False)
        rep_sid = self._reparse_sid
        if rep_sid is not None and rep_sid > 0:
            # 重新解析模式：更新已有图纸的 blocks_json + 实体
            db.update_sheet_blocks(rep_sid, blocks_json)
            db.update_sheet_status(rep_sid, "ready",
                                   entity_count=len(drawing.entities),
                                   layer_count=len(drawing.layers))
            db.replace_entities(rep_sid, drawing.entities)
            sid = rep_sid
            self._reparse_sid = None
        else:
            sid = db.add_sheet(self._project_id, os.path.basename(self._parse_src),
                               self._parse_src, dxf_path, "ready", 1.0,
                               len(drawing.entities), len(drawing.layers), blocks_json)
            db.replace_entities(sid, drawing.entities)

        self._current_blocks = drawing.blocks
        self._sheet_id = sid
        entities = db.get_entities(sid)
        self.canvas.build(entities, drawing.blocks)
        self.layer_tree.rebuild(
            [LayerInfo(name=k, entity_count=v, color=drawing.layer_colors.get(k, (128,128,128)))
             for k, v in sorted(drawing.layers.items(), key=lambda kv: kv[0].lower())],
            [BlockInfo(name=k, entity_count=v) for k, v in sorted(drawing.block_refs.items(), key=lambda kv: kv[0].lower())],
            layer_colors=drawing.layer_colors)

        self._reload_sheets()
        self._refresh_base_layers()
        self._stat_entities = len(drawing.entities)
        self._stat_layers = len(drawing.layers)
        self._update_stats()
        self._refresh_enabled()
        self.statusBar().showMessage(
            f"图纸就绪：{len(drawing.entities)} 实体 / {len(drawing.layers)} 图层 / "
            f"{len(drawing.block_refs)} 块")
        # 新图纸加入后刷新图例块清单
        if self._project_id is not None:
            self.legend_panel.load_project(self._project_id, self._sheet_id)
        self._parse_worker = None

    def _on_parse_failed(self, msg: str):
        self._set_busy(False)
        dlg = getattr(self, "_parse_dialog", None)
        if dlg is not None:
            dlg.close()
            self._parse_dialog = None
        if "ODA" in msg or "DWG" in msg:
            extra = "" if "解决方案" in msg else \
                "\n请安装 ODA File Converter（免费），或先在 CAD 中另存为 DXF。"
            QMessageBox.warning(self, "DWG 转换失败", f"{msg}{extra}")
        else:
            QMessageBox.critical(self, "解析失败", f"无法解析图纸：{msg}")
        self.statusBar().showMessage("就绪")
        self._parse_worker = None

    def _on_sheet_changed(self, row):
        if row < 0 or self._project_id is None:
            return
        started = time.perf_counter()
        sheets = db.get_sheets(self._project_id)
        if row >= len(sheets):
            return
        s = sheets[row]
        logger.info("sheet switch start: sheet_id=%s filename=%s", s.id, s.filename)
        self._sheet_id = s.id
        # 图例标定跟随当前图纸：只显示该图纸实际出现的设备块，方便逐图核对
        self.legend_panel.set_sheet_filter(s.id)
        # 切换图纸时清空待选
        if self.canvas.get_pending():
            self._clear_pending()
        # P1-1：切图数据加载后台化。序号防并发错乱：快速连续切换时旧 worker
        # 结果到达即丢弃；旧图 canvas 构建若在跑，则取消它。
        self._sheet_load_seq += 1
        if self._sheet_cancel_event is not None:
            self._sheet_cancel_event.set()
            self._sheet_cancel_event = None
        # 立即给用户反馈（后续真正完成时状态栏替换为「已加载」）
        self.statusBar().showMessage(f"正在加载 {s.filename}…")
        # DB 读取（blocks_json / 实体 / 图层统计）全部移出 UI 线程
        worker = _SheetLoadWorker(s.id, s.blocks_json)
        worker.data_ready.connect(
            lambda payload, seq=self._sheet_load_seq, s=s: self._on_sheet_data_ready(seq, payload, s))
        worker.failed.connect(self._on_sheet_load_failed)
        worker.start()
        self._sheet_worker = worker

    def _on_sheet_data_ready(self, seq: int, payload: dict, s):
        """后台 DB 读取完成 → 主线程分批构建画布 + 刷新图层树/状态。

        canvas.build 仍在此函数执行（QGraphicsItem 需 GUI 线程），但改为
        分批 + 每批 pump 事件循环：进度条走起来、窗口不再「未响应」。
        """
        if seq != self._sheet_load_seq:
            return  # 用户已切到别的图纸，丢弃过期结果
        started = time.perf_counter()
        blocks = payload["blocks"]
        entities = payload["entities"]
        layer_colors = payload["layer_colors"]
        layers = payload["layers"]
        blocks_info = payload["blocks_info"]
        self._current_blocks = blocks
        self._stat_entities = len(entities)
        self._stat_layers = len(layers)
        self._sheet_id = s.id

        cancel_evt = threading.Event()
        self._sheet_cancel_event = cancel_evt

        dlg = QProgressDialog(f"加载图纸：{s.filename}", "取消", 0, 100, self)
        dlg.setWindowTitle("加载中")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(cancel_evt.set)
        dlg.show()

        def progress(p):
            if not dlg.wasCanceled():
                dlg.setValue(int(p * 100))

        try:
            self.canvas.build(entities, blocks, progress_cb=progress,
                              cancel_event=cancel_evt)
        except Exception as e:  # noqa: BLE001
            dlg.close()
            self._sheet_cancel_event = None
            logger.exception("sheet build failed: sheet_id=%s", s.id)
            self.statusBar().showMessage(f"加载失败：{e}")
            return
        dlg.close()
        if cancel_evt.is_set():
            # 用户取消 / 已切图：不重复状态（下轮数据到达或新切图会重建）
            self._sheet_cancel_event = None
            return

        # ----- 构建完成：后续 UI 更新（图层树 / 状态条 / 跨图纸定位） -----
        self.layer_tree.rebuild(
            [LayerInfo(name=k, entity_count=v, color=layer_colors.get(k, (128, 128, 128)))
             for k, v in layers],
            [BlockInfo(name=k, entity_count=v) for k, v in blocks_info],
            layer_colors=layer_colors)
        note = "" if s.blocks_json else "（无块缓存，块引用将以红叉占位；请重新打开该图纸刷新）"
        self._stat_entities = len(entities)
        self._stat_layers = len(layers)
        self.canvas_toolbar.set_loaded_file(s.filename)
        self._refresh_status_breadcrumb()
        self.statusBar().showMessage(f"已加载：{s.filename}（{len(entities)} 实体）{note}")
        logger.info("sheet switch complete: sheet_id=%s filename=%s entities=%d layers=%d blocks=%d elapsed_ms=%.1f",
                    s.id, s.filename, len(entities), len(layers),
                    len(blocks_info), (time.perf_counter() - started) * 1000)
        # 跨图纸定位：图纸加载完成后自动触发定位
        pending = self._pending_locate_name
        if pending:
            self._pending_locate_name = None
            self._on_legend_locate(pending)
        self._refresh_enabled()

    def _on_sheet_load_failed(self, sheet_id: int, err: str):
        """后台 DB 读取失败（如数据库损坏/文件被删）→ 友好提示。"""
        logger.error("sheet load failed: sheet_id=%s err=%s", sheet_id, err.splitlines()[-1] if err else "")
        self.statusBar().showMessage(f"图纸数据加载失败：{(err or '').splitlines()[-1]}")

    # ---------- BOQ ----------
    def import_boq(self):
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先新建项目")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 BOQ 清单", "", "Excel 清单 (*.xlsx *.xls)")
        if not path:
            return
        items, mapping = boq_parser.parse_boq(path)
        if not items:
            QMessageBox.warning(self, "解析失败", "未识别到有效条目，请检查表头（编号/描述/单位）")
            return
        db.replace_boq_items(self._project_id, items)
        db.update_project_boq(self._project_id, path)
        self.boq_table.load(db.get_boq_items(self._project_id))
        self._stat_boq = len(items)
        self._refresh_boq_count()
        self._update_stats()
        self.statusBar().showMessage(f"BOQ 已导入：{len(items)} 条")

    def open_materials_dialog(self):
        """打开「主要材料表」对话框：设备块计数 + 导线长度 + BOQ 关联回写。"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        from .materials_dialog import MaterialsDialog
        dlg = MaterialsDialog(self._project_id, self)
        if dlg.exec() == QDialog.Accepted:
            # 关联/回写后刷新 BOQ 表（实测数量列可能已更新）
            self.boq_table.load(db.get_boq_items(self._project_id))
            self._stat_boq = len(db.get_boq_items(self._project_id))
            self._refresh_boq_count()
            self._update_stats()

    def open_project_settings(self):
        """打开「项目设置」对话框：图层/设备规则 + 图纸 BOQ 来源 + 元信息"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        from .project_settings_dialog import ProjectSettingsDialog
        dlg = ProjectSettingsDialog(self._project_id, self)
        if dlg.exec() == QDialog.Accepted:
            # 保存后刷新相关视图
            self._reload_sheets()
            self.legend_panel.load_project(self._project_id)
            self.binding_workbench.load_project(self._project_id)

    # ----- 任务二十九 P5：LLM 设置中心接线 -----
    def open_llm_settings(self):
        """打开「LLM 设置中心」对话框：5 backend + 测速 + Fallback"""
        from .llm_settings_dialog import LLMSettingsDialog
        try:
            dlg = LLMSettingsDialog(self)
            dlg.exec()
            self._refresh_llm_status()
            self.statusBar().showMessage("LLM 设置已更新", 4000)
        except Exception as e:  # noqa: BLE001
            self._error_box(
                "LLM 设置失败", "无法打开 LLM 设置窗口。\n\n"
                "请检查配置目录读写权限后重试。", f"{e}")

    # ---------- P1-2 数据库瘦身（VACUUM） ----------
    VACUUM_WASTE_RATIO = 0.4          # 空闲页 ≥ 40% 即认为高碎片，值得整理
    VACUUM_MIN_BYTES = 100 * 1024 * 1024  # <100MB 的库不值得动（收益小）

    def _check_db_fragmentation(self):
        """启动检测：freelist 占比过高（如历史删除遗留下来的空闲页）→ 提示整理。

        纯展示性检查失败（PRAGMA 查询 / DB 不存在）静默跳过，不影响启动。
        """
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        try:
            u = db.db_usage()
            if not u["exists"]:
                return
            fbytes = u["freelist_bytes"]
            if (fbytes >= self.VACUUM_MIN_BYTES
                    and u["waste_ratio"] >= self.VACUUM_WASTE_RATIO):
                ret = QMessageBox.question(
                    self, "数据库瘦身",
                    f"数据库文件 {u['file_bytes']/1e6:.0f} MB，其中空闲页约占 "
                    f"{u['waste_ratio']:.0%}（{fbytes/1e6:.1f} MB）可回收。\n\n"
                    "整理（VACUUM）可显著缩小文件、加快冷启动。是否现在整理？",
                    QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    self._run_vacuum()
        except Exception:  # noqa: BLE001
            logger.debug("db fragmentation check skipped", exc_info=True)

    def open_db_maintenance(self):
        """工具菜单入口：手动查看/整理数据库空间（不设自动触发条件）。"""
        try:
            u = db.db_usage()
        except Exception as e:  # noqa: BLE001
            self._error_box("数据库瘦身", "无法读取数据库状态。", f"{e}")
            return
        if not u["exists"]:
            QMessageBox.information(self, "数据库瘦身", "数据库文件暂不存在。")
            return
        txt = (f"数据库文件：{u['file_bytes']/1e6:.0f} MB\n"
               f"空闲页：{u['free_pages']:,} 页（{u['freelist_bytes']/1e6:.1f} MB，"
               f"占比 {u['waste_ratio']:.0%}）\n\n"
               "VACUUM 会回收历史删除留下的空闲页，文件体积显著缩小。\n"
               "大库需数秒～数十秒，期间界面仍可操作。")
        ret = QMessageBox.question(self, "数据库瘦身 (VACUUM)", txt,
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self._run_vacuum()

    def _run_vacuum(self):
        """后台执行 VACUUM：进度对话框（进度条不确定）展示忙碌，完成后报结果。"""
        dlg = QProgressDialog("VACUUM 整理中…", "关闭", 0, 0, self)
        dlg.setWindowTitle("数据库瘦身")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setCancelButton(None)
        dlg.show()
        w = _VacuumWorker(self)

        def _done(res):
            dlg.close()
            freed_mb = res["freed_bytes"] / 1e6
            QMessageBox.information(
                self, "数据库瘦身完成",
                f"整理完成：{res['before_bytes']/1e6:.0f} MB → "
                f"{res['after_bytes']/1e6:.0f} MB\n"
                f"回收 {freed_mb:.1f} MB，用时 {res['duration_ms']/1000:.1f}s")

        def _fail(err):
            dlg.close()
            self._error_box("数据库瘦身", "VACUUM 执行失败，请检查磁盘空间/权限。", err)

        w.finished_ok.connect(_done)
        w.failed.connect(_fail)
        w.start()
        self._vacuum_worker = w   # 持有引用，防 GC

    def _error_box(self, title: str, hint: str, detail: str = ""):
        """友好错误弹窗入口：堆栈收进「显示详情」，面向用户只给原因+建议。"""
        from .ui_utils import error_box
        error_box(self, title, hint, detail)

    def warning_box(self, title: str, hint: str, detail: str = ""):
        """友好警告弹窗入口（同上，级别为警告）。"""
        from .ui_utils import warning_box
        warning_box(self, title, hint, detail)

    def _refresh_llm_status(self):
        """更新状态栏 LLM 标签：显示当前激活 backend + model + fallback 标识。"""
        try:
            s = db.get_llm_settings()
            active = s.get("active_backend", "ollama")
            model_map = {
                "ollama": s.get("ollama_model", ""),
                "dashscope": s.get("dashscope_model", ""),
                "openai": s.get("openai_model", ""),
                "deepseek": s.get("deepseek_model", ""),
                "custom": s.get("custom_model", ""),
            }
            model = model_map.get(active, "")
            fb_mark = " 〔+FB〕" if s.get("fallback_enabled") and s.get("fallback_backend") else ""
            self._llm_status_label.setText(f"LLM: {active}/{model}{fb_mark}")
        except Exception:  # noqa: BLE001
            self._llm_status_label.setText("LLM: ?")

    def repair_boq(self):
        """对已入库 BOQ 做合同段落过滤 + 列位号自愈（不重新导入 Excel）。"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        res = db.reparse_boq(self._project_id)
        self.boq_table.load(db.get_boq_items(self._project_id))
        self._stat_boq = len(db.get_boq_items(self._project_id))
        self._refresh_boq_count()
        self._update_stats()
        self.legend_panel.load_project(self._project_id)
        self.binding_workbench.load_project(self._project_id)
        QMessageBox.information(
            self, "BOQ 已自愈",
            f"删除合同声明段落 {res['removed']} 行\n修正列错位 {res['fixed_cols']} 行\n\n"
            "建议随后点击「绑定工作台 → 生成候选」让规则重新评估所有 BOQ 条目。")

    def export_layer_list(self):
        """导出当前项目所有图层的实体数+块名样本 → xlsx，便于维护设备/导线白名单。

        列出每一图层：
        - 图层名
        - 实体数（entity）/ 引用块数
        - 块名样本（前 3 个）
        - 推断分类建议（基于已有 BUILDING_BG_KEYWORDS 判断）
        """
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出图层清单", f"project_{self._project_id}_layers.xlsx",
            "Excel (*.xlsx *.csv)")
        if not path:
            return
        try:
            rows = db.summarize_layers(self._project_id)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"读取图层汇总失败: {e}")
            return
        if not rows:
            QMessageBox.information(self, "无数据", "当前项目未识别到任何图层")
            return
        # 推断分类建议
        from app.engineering.classifier import _is_building_bg_layer
        sug = []
        for r in rows:
            layer = r["layer_name"] or ""
            if not layer or layer == "0":
                sug.append("默认图层(空)")
            elif _is_building_bg_layer(layer):
                sug.append("建筑背景(应跳过)")
            else:
                sug.append("机电子件(保留)")
        # 写文件
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "图层汇总"
            ws.append(["图层名", "实体数", "块种类数", "块名样本", "推断分类"])
            for r, s in zip(rows, sug):
                ws.append([r["layer_name"], r["entity_count"],
                           r["block_count"], "; ".join(r["block_samples"] or []), s])
            if path.endswith(".csv"):
                # 用户给的是 csv 路径，转写
                import csv
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["图层名", "实体数", "块种类数", "块名样本", "推断分类"])
                    for r, s in zip(rows, sug):
                        w.writerow([r["layer_name"], r["entity_count"],
                                    r["block_count"], "; ".join(r["block_samples"] or []), s])
            else:
                wb.save(path)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))
            return
        building_n = sum(1 for s in sug if "建筑背景" in s)
        mep_n = sum(1 for s in sug if "机电子件" in s)
        QMessageBox.information(
            self, "导出完成",
            f"已导出 {len(rows)} 个图层到：\n{path}\n\n"
            f"其中建筑背景 {building_n} 个，机电子件 {mep_n} 个。\n\n"
            "请把文件发回（仅保留「机电子件」/真设备/导线层），"
            "我将据此更新 app/config.py 的白名单。")

    # ---------- 条目选择 ----------
    def _on_item_selected(self, item_id: int):
        self._current_item_id = item_id
        for it in db.get_boq_items(self._project_id or 0):
            if it.id == item_id:
                self._current_item_desc = f"{it.code} {it.description}".strip()
                break
        self.mapping_panel.set_current(self._current_item_desc or "未选择")
        self._refresh_mappings(item_id)
        # Phase 3 跨高亮：BOQ → 画布（fitInView + flash）
        if self._sheet_id:
            ms = db.get_mappings(item_id, self._sheet_id)
            eids = []
            for m in ms:
                eids.extend(map_svc.resolve_entity_ids(self._sheet_id, m))
            if eids:
                self.canvas.flash_entities(eids[:50])  # 上限 50 防卡顿

    def _current_item(self) -> BoqItem | None:
        if not self._current_item_id or self._project_id is None:
            return None
        for it in db.get_boq_items(self._project_id):
            if it.id == self._current_item_id:
                return it
        return None

    # ---------- 映射 ----------
    def _do_associate(self, entity_ids: list):
        """BOQ-first 模式（兼容老路径）：直接关联到当前 BOQ 条目"""
        item = self._current_item()
        if item is None:
            self.statusBar().showMessage("请先在右侧选择一条 BOQ 条目")
            return
        if self._sheet_id is None:
            self.statusBar().showMessage("请先打开图纸")
            return
        before_ids = self._mapping_ids_for(item.id)
        added, conflicts = map_svc.add_entity_mapping(item.id, self._sheet_id, entity_ids)
        if added:
            self._push_undo(("rollback_assoc", item.id, self._sheet_id, before_ids))
        msg = f"已关联 {added} 个实体到 [{item.code}]"
        if conflicts:
            msg += f"；{len(conflicts)} 个实体已被其他条目映射（跳过）"
        self.statusBar().showMessage(msg)
        self.canvas.color_mapped_entities(item.id,
            map_svc.mapped_entity_ids(item.id, self._sheet_id))
        self._recalc_and_refresh(item.id)

    def _on_entity_picked(self, entity_id: int):
        if self._mode == "pick":
            self._add_pending([entity_id], additive=False)
        else:
            self._do_associate([entity_id])

    def _on_entities_picked(self, entity_ids: list):
        if self._mode == "pick":
            self._add_pending(entity_ids, additive=False)
        else:
            self._do_associate(entity_ids)

    def _add_pending(self, eids: list, additive: bool = True):
        """Phase 3: 拾取模式累积。additive=True 时 Shift 多选切换状态。"""
        if not additive:
            self.canvas.clear_pending()
            new_set = set(eids)
        else:
            # 累加：已存在则移除，否则添加
            cur = set(self.canvas.get_pending())
            for eid in eids:
                if eid in cur:
                    cur.discard(eid)
                else:
                    cur.add(eid)
            new_set = cur
        self.canvas.set_pending(list(new_set))
        self.selection_bar.set_pending_count(len(new_set))
        self._sync_entity_props()
        # 反向定位第一个被选实体的 BOQ（如果存在）
        if len(new_set) == 1:
            only = next(iter(new_set))
            self._cross_highlight_from_canvas(only)

    def _cross_highlight_from_canvas(self, eid: int):
        """画布点选 → 反查 BOQ 条目并高亮"""
        if not self._project_id:
            return
        boq_id = self._find_boq_for_entity(eid)
        if boq_id:
            self.boq_table.highlight_item(boq_id, flash=True, select=False)
            self.canvas.flash_entities([eid])

    def _find_boq_for_entity(self, eid: int) -> int | None:
        """在当前图纸中找映射了该 eid 的 BOQ 条目"""
        if not self._sheet_id:
            return None
        for it in self.boq_table.all_items():
            ms = db.get_mappings(it.id, self._sheet_id)
            for m in ms:
                if m.mode == "entity" and m.entity_id == eid:
                    return it.id
                if m.mode in ("layer", "block"):
                    ids = map_svc.resolve_entity_ids(self._sheet_id, m)
                    if eid in ids:
                        return it.id
        return None

    # ---------- 撤销（P0-8） ----------
    def _push_undo(self, action: tuple):
        """入站撤销记录（cap 50）。"""
        self._undo_stack.append(action)
        if len(self._undo_stack) > 50:
            del self._undo_stack[0]

    def _mapping_ids_for(self, item_id: int) -> set:
        return {m.id for m in db.get_mappings(item_id, self._sheet_id)}

    def _post_mapping_change(self):
        """映射变更后的统一刷新：重新着色 + 防抖重算。"""
        item = self._current_item()
        if item is not None and self._sheet_id is not None:
            self.canvas.color_mapped_entities(item.id,
                map_svc.mapped_entity_ids(item.id, self._sheet_id))
            self._recalc_and_refresh(item.id)

    def _undo_last(self):
        """Ctrl+Z：撤销最近一次映射变更（关联/删除）。输入框聚焦时不拦截文本撤销。"""
        from PySide6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        focus = QApplication.focusWidget()
        if focus is not None and isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus.undo()
            return
        if not self._undo_stack:
            self.statusBar().showMessage("没有可撤销的操作")
            return
        action = self._undo_stack.pop()
        kind = action[0]
        try:
            if kind == "restore_mapping":
                # 撤销删除：按捕获的行重建映射
                bi, mode, eid, layer, block = action[1]
                sheet = action[2]
                db.add_mapping(bi, sheet, mode,
                               entity_id=eid, layer_name=layer, block_name=block)
                self._post_mapping_change()
                self.statusBar().showMessage("已撤销：恢复刚删除的映射")
            elif kind == "rollback_assoc":
                # 撤销关联：删除该次新增的映射（快照之后的 id）
                item_id, sheet, before_ids = action[1], action[2], action[3]
                for m in db.get_mappings(item_id, sheet):
                    if m.id not in before_ids:
                        db.delete_mapping(m.id)
                if item_id == self._current_item_id:
                    self._post_mapping_change()
                self.statusBar().showMessage("已撤销上次关联")
            else:
                self.statusBar().showMessage(f"未知撤销操作：{kind}")
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"撤销失败：{e}")

    def _commit_pending(self):
        """按 Enter / 点分配 → 把待选区提交到当前 BOQ 行"""
        if not self.canvas.get_pending():
            return
        item = self._current_item()
        if item is None:
            self.statusBar().showMessage("请先在右侧选择一条 BOQ 条目")
            return
        eids = self.canvas.get_pending()
        before_ids = self._mapping_ids_for(item.id)
        added, conflicts = map_svc.add_entity_mapping(item.id, self._sheet_id, eids)
        if added:
            self._push_undo(("rollback_assoc", item.id, self._sheet_id, before_ids))
        msg = f"已分配 {added} 个实体到 [{item.code}]"
        if conflicts:
            msg += f"；{len(conflicts)} 冲突跳过"
        self.statusBar().showMessage(msg)
        self.canvas.clear_pending()
        self.selection_bar.set_pending_count(0)
        self._sync_entity_props()
        self.canvas.color_mapped_entities(item.id,
            map_svc.mapped_entity_ids(item.id, self._sheet_id))
        self._recalc_and_refresh(item.id)

    def _sync_entity_props(self):
        """实体属性面板跟随画布待选变化（v3）。"""
        self.entity_properties.update_from_summary(self.canvas.pending_summary())

    def _clear_pending(self):
        self.canvas.clear_pending()
        self.selection_bar.set_pending_count(0)
        self._sync_entity_props()

    def _on_layer_associate(self, layer: str):
        item = self._current_item()
        if item is None:
            self.statusBar().showMessage("请先在右侧选择一条 BOQ 条目")
            return
        before_ids = self._mapping_ids_for(item.id)
        added, conflicts = map_svc.add_layer_mapping(item.id, self._sheet_id, layer)
        if added:
            self._push_undo(("rollback_assoc", item.id, self._sheet_id, before_ids))
        self.statusBar().showMessage(f"图层 [{layer}] 已关联 {added} 实体" +
                                     (f"；{len(conflicts)} 冲突跳过" if conflicts else ""))
        self.canvas.color_mapped_entities(item.id,
            map_svc.mapped_entity_ids(item.id, self._sheet_id))
        self._recalc_and_refresh(item.id)

    def _on_block_associate(self, block: str):
        item = self._current_item()
        if item is None:
            self.statusBar().showMessage("请先在右侧选择一条 BOQ 条目")
            return
        before_ids = self._mapping_ids_for(item.id)
        added, conflicts = map_svc.add_block_mapping(item.id, self._sheet_id, block)
        if added:
            self._push_undo(("rollback_assoc", item.id, self._sheet_id, before_ids))
        self.statusBar().showMessage(f"块 [{block}] 已关联 {added} 个引用（计数规则）" +
                                     (f"；{len(conflicts)} 冲突跳过" if conflicts else ""))
        self.canvas.color_mapped_entities(item.id,
            map_svc.mapped_entity_ids(item.id, self._sheet_id))
        self._recalc_and_refresh(item.id)

    def _on_layer_lock(self, layer: str, locked: bool):
        """锁定：把图层淡化到 15% 透明度（仍可见但提示不可用）"""
        if locked:
            self.canvas.set_layer_opacity(layer, 38)
            self.statusBar().showMessage(f"图层 [{layer}] 已锁定（淡化 15%）")
        else:
            self.canvas.set_layer_opacity(layer, 255)
            self.statusBar().showMessage(f"图层 [{layer}] 已解锁")

    def _on_layer_color_override(self, layer: str, color):
        """颜色覆盖：刷新该图层所有 item 的 pen/brush 颜色"""
        if color is None:
            self.statusBar().showMessage(f"图层 [{layer}] 颜色覆盖已清除（需重新打开图纸）")
            return
        items = self.canvas._layer_items.get(layer, [])
        for item in items:
            if hasattr(item, "pen"):
                pen = item.pen()
                pen.setColor(QColor(*color))
                item.setPen(pen)
            if hasattr(item, "brush"):
                brush = item.brush()
                brush.setColor(QColor(*color))
                item.setBrush(brush)
        self.statusBar().showMessage(f"图层 [{layer}] 颜色已覆盖为 RGB{color}")

    def _on_delete_mapping(self, mid: int):
        """删除映射（带确认，P0-8；删除可 Ctrl+Z 撤销）。"""
        sheet_id = self._sheet_id
        # 捕获被删映射的完整行用于撤销重建
        m_row = None
        for it in (db.get_boq_items(self._project_id) if self._project_id else []):
            for m in db.get_mappings(it.id, sheet_id):
                if m.id == mid:
                    m_row = (it.id, m.mode, m.entity_id, m.layer_name or "", m.block_name or "")
                    break
            if m_row:
                break
        if m_row is None:
            return
        target = (m_row[2] and f"实体#{m_row[2]}") or m_row[3] or m_row[4] or "?"
        ret = QMessageBox.question(
            self, "删除映射",
            f"确定删除这条映射？\n方式：{m_row[1]} · 目标:{target}\n\n"
            "删除后该条目将不再计入此映射的计量。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        self._push_undo(("restore_mapping", m_row, sheet_id))
        db.delete_mapping(mid)
        self._post_mapping_change()
        self.statusBar().showMessage("映射已删除（Ctrl+Z 可撤销）")

    # ---------- 计量 / 刷新 ----------
    def _refresh_mappings(self, item_id: int):
        if self._sheet_id is None:
            self.mapping_panel.load_mappings([], {})
            return
        import time as _time
        _started = _time.perf_counter()
        ms = db.get_mappings(item_id, self._sheet_id)
        counts = {}
        for m in ms:
            counts[m.id] = len(map_svc.resolve_entity_ids(self._sheet_id, m))
        self.mapping_panel.load_mappings(ms, counts)
        logger.debug("refresh_mappings: item_id=%s mappings=%d elapsed_ms=%.1f",
                     item_id, len(ms), (_time.perf_counter() - _started) * 1000)

    def _recalc_and_refresh(self, item_id: int = None):
        """计量重算（300ms 防抖）：连续 rule/scale/绑定变更合并为一次，
        避免大 BOQ 清单每改一格都触发全量同步计量卡顿 UI。"""
        self._recalc_pending_item = item_id
        if self._recalc_timer is None:
            self._recalc_timer = QTimer(self)
            self._recalc_timer.setSingleShot(True)
            self._recalc_timer.timeout.connect(self._do_recalc)
        self._recalc_timer.start(300)

    def _do_recalc(self):
        self._recalc_timer.stop()
        if self._project_id is None or self._sheet_id is None:
            return
        item_id = self._recalc_pending_item
        import time as _time
        _started = _time.perf_counter()
        items = db.get_boq_items(self._project_id)
        for it in items:
            if item_id is not None and it.id != item_id:
                continue
            res = measure.compute_item(it, self._sheet_id, sheet_scale=1.0)
            self.boq_table.update_result(it.id, res["count"], res["qty"])
            if it.id == self._current_item_id:
                self.mapping_panel.set_result(
                    res["qty"], res["count"],
                    [f"#{d['entity_id']} {d['handle']} → {d['qty']:g}" for d in res["detail"]],
                    res["factor"])
        if item_id:
            self._refresh_mappings(item_id)
        logger.debug("recalc_and_refresh: project_id=%s sheet_id=%s items=%d target=%s elapsed_ms=%.1f",
                     self._project_id, self._sheet_id, len(items),
                     item_id or "all", (_time.perf_counter() - _started) * 1000)

    # ---------- 导出 ----------
    def export_report(self):
        if self._project_id is None or self._sheet_id is None:
            QMessageBox.information(self, "提示", "请先打开图纸并导入 BOQ")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出算量清单", "算量清单.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        # P3：导出对话框选「用实测值覆盖原数量」→ 数量列用 measured_qty
        from PySide6.QtWidgets import QCheckBox, QDialogButtonBox, QVBoxLayout, QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("导出选项")
        lay = QVBoxLayout(dlg)
        chk = QCheckBox("数量列使用实测数量（measured_qty 回写值）")
        chk.setToolTip("勾选后导出清单的「图纸计量数量」列用已回写的实测数量列（原数量保留对照）")
        lay.addWidget(chk)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        n = report.export_report(self._project_id, self._sheet_id, path,
                                 use_measured=chk.isChecked())
        QMessageBox.information(self, "导出成功", f"已导出 {n} 条清单 →\n{path}")

    # ---------- AI 自动算量（v3 22/23 号） ----------
    def ai_takeoff_current(self):
        """AI 算量（当前图纸）：对画布正在显示的图纸直接算量，不重新选文件。"""
        if self._project_id is None or self._sheet_id is None:
            QMessageBox.information(self, "提示", "请先打开一张图纸（或选「AI 自动算量（单图…）」）")
            return
        sheet = next((s for s in db.get_sheets(self._project_id) if s.id == self._sheet_id), None)
        if sheet is None:
            QMessageBox.information(self, "提示", "未找到当前图纸信息")
            return
        path = sheet.src_path or sheet.dxf_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(
                self, "AI 算量",
                f"当前图纸的源文件不存在：\n{path}\n\n"
                "图纸可能已被移动/删除，请改用「AI 自动算量（单图…）」重新选择文件。")
            return
        self._run_ai_takeoff_single(path)

    def ai_takeoff_single(self):
        """单图 AI 算量入口"""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图纸", "", "CAD 文件 (*.dwg *.dxf)"
        )
        if not path:
            return
        self._run_ai_takeoff_single(path)

    def ai_takeoff_folder(self):
        """文件夹 AI 算量入口"""
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹")
        if not folder:
            return
        self._run_ai_takeoff_folder(folder)

    def _run_ai_takeoff_single(self, path: str):
        """启动单图 AI 算量后台线程"""
        from app.takeoff.orchestrator import TakeoffConfig
        legend = db.get_block_legend_map(self._project_id) if self._project_id else {}
        self._ai_worker = _AiTakeoffWorker(path=path, config=TakeoffConfig(), legend=legend)
        self._ai_worker.progress.connect(self._on_ai_progress)
        self._ai_worker.finished_ok.connect(self._on_ai_single_done)
        self._ai_worker.failed.connect(self._on_ai_failed)
        self._ai_dialog = QProgressDialog("AI 算量中...", "取消", 0, 0, self)
        self._ai_dialog.setWindowModality(Qt.WindowModal)
        self._ai_dialog.setWindowTitle("AI 自动算量")
        self._ai_dialog.show()
        self._set_busy(True)
        self._ai_worker.start()

    def _run_ai_takeoff_folder(self, folder: str):
        """启动文件夹 AI 算量后台线程"""
        from app.takeoff.orchestrator import TakeoffConfig
        from pathlib import Path
        legend = db.get_block_legend_map(self._project_id) if self._project_id else {}
        self._ai_worker = _AiTakeoffFolderWorker(folder=Path(folder), config=TakeoffConfig(),
                                                 legend=legend)
        self._ai_worker.progress.connect(self._on_ai_progress)
        self._ai_worker.finished_ok.connect(self._on_ai_folder_done)
        self._ai_worker.failed.connect(self._on_ai_failed)
        self._ai_dialog = QProgressDialog("文件夹 AI 算量中...", "取消", 0, 0, self)
        self._ai_dialog.setWindowModality(Qt.WindowModal)
        self._ai_dialog.setWindowTitle("AI 自动算量 - 文件夹")
        self._ai_dialog.show()
        self._set_busy(True)
        self._ai_worker.start()

    def _on_ai_progress(self, phase: str, progress: float, msg: str):
        dlg = getattr(self, "_ai_dialog", None)
        if dlg is None:
            return
        if not dlg.labelText() or phase not in dlg.labelText():
            dlg.setLabelText(f"【{phase}】{msg}")

    def _on_ai_single_done(self, result):
        self._set_busy(False)
        dlg = getattr(self, "_ai_dialog", None)
        if dlg:
            dlg.close()
            self._ai_dialog = None
        # 显示结果对话框
        from app.ui.ai_results_dialog import AiResultsDialog
        d = AiResultsDialog(result.items, project_name="单图", parent=self)
        d.accepted.connect(self._on_ai_accept)   # 接受 → 保存到 BOQ 并刷新
        d.exec()

    def _on_ai_folder_done(self, result):
        self._set_busy(False)
        dlg = getattr(self, "_ai_dialog", None)
        if dlg:
            dlg.close()
            self._ai_dialog = None
        from app.ui.ai_results_dialog import AiResultsDialog
        d = AiResultsDialog(result.items, project_name=result.project_name, parent=self)
        d.accepted.connect(self._on_ai_accept)
        d.exec()

    def _on_ai_accept(self, items: list):
        """接受 AI 算量结果：转 BoqItem 追加到项目 BOQ 清单并刷新显示"""
        if self._project_id is None:
            QMessageBox.information(self, "提示", "请先选择项目再接受 AI 结果")
            return
        from app.models import BoqItem
        existing = db.get_boq_items(self._project_id)
        next_row = max([i.row_index for i in existing], default=0) + 1
        unit2rule = {"m": "length", "m²": "area", "m2": "area", "m3": "area",
                     "个": "count", "套": "count", "台": "count", "组": "count"}
        new_items = []
        for it in items:
            new_items.append(BoqItem(
                project_id=self._project_id,
                row_index=next_row + len(new_items),
                code=it.code,
                description=it.description,
                unit=it.unit or "个",
                original_qty=float(it.quantity or 0),
                rule_type=unit2rule.get(str(it.unit), "count"),
                scale_factor=1.0))
        if not new_items:
            return
        db.append_boq_items(self._project_id, new_items)
        self.boq_table.load(db.get_boq_items(self._project_id))
        self._stat_boq = len(db.get_boq_items(self._project_id))
        self._refresh_boq_count()
        self._update_stats()
        self.right_tabs.setCurrentWidget(self.boq_page)
        self.statusBar().showMessage(
            f"已保存 {len(new_items)} 条 AI 结果到 BOQ 清单（追加，未覆盖已有条目）")

    def _on_ai_failed(self, err: str):
        self._set_busy(False)
        dlg = getattr(self, "_ai_dialog", None)
        if dlg:
            dlg.close()
            self._ai_dialog = None
        self._error_box("AI 算量失败",
                        "AI 算量未能完成。\n\n"
                        "常见原因：\n"
                        "· LLM 后端未配置或未启动（检查「更多 → LLM 设置…」）\n"
                        "· 图纸解析失败或文件损坏\n"
                        "· 网络超时（可在 LLM 设置中调大 timeout）\n\n"
                        "点击「显示详情」可查看完整错误信息。",
                        err)

    # ---------- 帮助 ----------
    def show_help(self):
        """使用说明：富文本 + 快捷键表（F1），比纯文本 QMessageBox 更易读。"""
        from PySide6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout, QPushButton, QHBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("使用说明")
        dlg.resize(660, 560)
        tb = QTextBrowser(dlg)
        tb.setOpenExternalLinks(True)
        tb.setHtml(_HELP_HTML)
        lay = QVBoxLayout(dlg)
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("关闭")
        ok.setObjectName("primaryBtn")
        ok.setMinimumWidth(88)
        ok.clicked.connect(dlg.accept)
        row.addWidget(ok)
        lay.addLayout(row)
        dlg.exec()

    # ---------- 项目属性 ----------
    def focus_project_properties(self):
        self.right_tabs.setCurrentWidget(self.project_properties)

    # ---------- 图例标定 ----------
    def focus_legend(self):
        self.right_tabs.setCurrentWidget(self.legend_panel)
        if self._project_id is not None:
            self.legend_panel.set_sheet_filter(self._sheet_id)

    # ---------- 绑定工作台 ----------
    def focus_binding(self):
        self.right_tabs.setCurrentWidget(self.binding_workbench)
        if self._project_id is not None:
            self.binding_workbench.load_project(self._project_id)

    def _on_binding_locate(self, sheet_id: int, name: str):
        """在画布中定位（支持跨图纸：切图纸 → 等加载完成 → 定位）"""
        if not name:
            self.statusBar().showMessage("无可定位名称")
            return
        # 目标图纸就是当前图纸，直接定位（同图例标定）
        if sheet_id == self._sheet_id:
            self._on_legend_locate(name)
            return
        # 需要切换图纸：存 pending 定位，切图纸后 _on_sheet_changed 末尾自动触发
        self._pending_locate_name = name
        sheets = db.get_sheets(self._project_id)
        for idx, s in enumerate(sheets):
            if s.id == sheet_id:
                self.sheet_list.setCurrentRow(idx)
                # _on_sheet_changed 会同步执行，末尾检查 _pending_locate_name 并触发定位
                return
        self.statusBar().showMessage("未找到目标图纸")

    def _on_legend_locate(self, block_name: str):
        """在画布中定位块：闪烁所有引用提示位置，放大聚焦首个引用看清块形态"""
        if self._sheet_id is None:
            self.statusBar().showMessage("请先打开图纸")
            return
        ids = [e.id for e in db.get_entities(self._sheet_id, block=block_name)]
        if not ids:
            self.statusBar().showMessage(f"当前图纸未找到块 [{block_name}] 的引用")
            return
        self.right_tabs.setCurrentWidget(self.boq_page)
        self.canvas.flash_entities(ids[:80])
        self.canvas.highlight_entities(ids)          # 定位高亮：目标原色+虚线框，其余变暗
        # 引用可能遍布全图：聚焦单个引用放大（看清块形态），闪烁提示其余位置
        self.canvas.zoom_to_entities(ids[:1])
        # v3：画布内浮标签（缩放级别无关，2.4s 自动消失）
        self.canvas.show_tag(f"定位：{block_name} ×{len(ids)}", ids[:1])
        self.statusBar().showMessage(
            f"定位块 [{block_name}]：{len(ids)} 个引用（已高亮，ESC/点击空白取消）")
