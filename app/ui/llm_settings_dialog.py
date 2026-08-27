"""LLM 设置对话框（简化版）：只保留 OpenAI 兼容协议。

单表单：接入地址(base_url) + API Key + 模型名 + embedding 模型名 + 测试连接。
- 复用 db.llm_settings 的 custom_* 字段（custom_base_url/custom_api_key/custom_model），
  不迁移表结构，向后兼容。
- 测速后台线程：probe_backend 不阻塞 UI。
- 保存写 db.llm_settings（白名单字段）。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QGroupBox, QCheckBox,
    QMessageBox, QPlainTextEdit,
)

from .. import db
from ..takeoff.llm_backends import LLMConfig
from ..llm.settings import probe_backend
from . import theme as T


# ============== 后台测速线程 ==============
class ProbeWorker(QThread):
    """后台探测 OpenAI 兼容端点连通性，避免阻塞 UI。"""
    finished_ok = Signal(dict)        # {"ok", "latency_ms", "models_sample", "error"}
    def __init__(self, llmc: LLMConfig, timeout: float = 5.0):
        super().__init__()
        self.llmc = llmc
        self.timeout = timeout
    def run(self):
        try:
            r = probe_backend("custom", self.llmc, timeout=self.timeout)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "latency_ms": 0, "models_sample": [], "error": str(e)}
        self.finished_ok.emit(r)


# ============== 主对话框 ==============
class LLMSettingsDialog(QDialog):
    """LLM 配置对话框（OpenAI 兼容协议单表单）。

    布局：
    - 顶部状态条：当前激活后端 / 上次保存时间 / 近 500 次调用 Tokens
    - 单表单：接入地址 / API Key / 模型名 / embedding 模型名
    - 底部：测试连接 / 保存 / 取消
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ LLM 设置")
        self.setStyleSheet(T.MAIN_QSS)
        self.setMinimumSize(560, 420)
        from .ui_utils import fit_dialog_to_screen
        fit_dialog_to_screen(self, (640, 520), "medium")

        self._settings = db.get_llm_settings()
        self._build_ui()
        self._refresh_status_bar()

    # ---------- UI 构建 ----------
    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        # 顶部状态条
        self.status_group = QGroupBox("当前状态")
        sg = QHBoxLayout(self.status_group)
        self.lbl_active = QLabel("—")
        self.lbl_active.setStyleSheet(f"font-size:{T.FONT_SIZE_SECTION}px;color:{T.ACCENT};font-weight:bold")
        self.lbl_updated = QLabel("—")
        self.lbl_updated.setStyleSheet(f"color:{T.TEXT_SECONDARY}")
        self.lbl_cost = QLabel("—")
        self.lbl_cost.setStyleSheet(f"color:{T.TEXT_SECONDARY}")
        sg.addWidget(QLabel("激活:"))
        sg.addWidget(self.lbl_active)
        sg.addSpacing(24)
        sg.addWidget(self.lbl_updated)
        sg.addSpacing(24)
        sg.addWidget(self.lbl_cost)
        sg.addStretch(1)
        v.addWidget(self.status_group)

        # 单表单（OpenAI 兼容协议）
        form_group = QGroupBox("OpenAI 兼容接入")
        fg = QFormLayout(form_group)
        fg.setSpacing(8)
        fg.setLabelAlignment(Qt.AlignRight)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1 或本地端点 http://127.0.0.1:11434/v1")
        self.base_url_edit.setMinimumWidth(360)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...（本地端点可留空）")
        self.api_key_edit.setMinimumWidth(360)

        self.show_key_check = QCheckBox("显示 API Key")
        self.show_key_check.toggled.connect(
            lambda on: self.api_key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("模型名（例：gpt-4o-mini / qwen2.5:7b / deepseek-chat）")
        self.model_edit.setMinimumWidth(360)

        self.embedding_model_edit = QLineEdit()
        self.embedding_model_edit.setPlaceholderText("embedding 模型名（例：text-embedding-3-small，可留空）")
        self.embedding_model_edit.setMinimumWidth(360)

        fg.addRow("接入地址:", self.base_url_edit)
        fg.addRow("API Key:", self.api_key_edit)
        fg.addRow("", self.show_key_check)
        fg.addRow("模型名:", self.model_edit)
        fg.addRow("Embedding 模型:", self.embedding_model_edit)
        v.addWidget(form_group)

        # 测试连接 + 状态
        test_row = QHBoxLayout()
        self.ollama_btn = QPushButton("🖥 检测本地 Ollama")
        self.ollama_btn.setToolTip(
            "自动探测本机 Ollama（http://127.0.0.1:11434），列出可用模型并填入表单。\n"
            "Ollama 走 OpenAI 兼容协议，接入地址填 http://127.0.0.1:11434/v1")
        self.ollama_btn.clicked.connect(self._on_detect_ollama)
        self.test_btn = QPushButton("🔌 测试连接")
        self.test_btn.clicked.connect(self._on_test)
        self.status_label = QLabel("—")
        self.status_label.setStyleSheet(f"color:{T.TEXT_SECONDARY}")
        test_row.addWidget(self.ollama_btn)
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.status_label, 1)
        v.addLayout(test_row)

        # 模型样本（测速后填充）
        self.models_box = QPlainTextEdit()
        self.models_box.setReadOnly(True)
        self.models_box.setPlaceholderText("测试成功后这里显示可用模型样本...")
        self.models_box.setMaximumHeight(90)
        v.addWidget(self.models_box)

        # 底部按钮
        row = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(self.save_btn)
        row.addWidget(self.cancel_btn)
        v.addLayout(row)

        # 填充当前值
        self.base_url_edit.setText(self._settings.get("custom_base_url", "") or "")
        self.api_key_edit.setText(self._settings.get("custom_api_key", "") or "")
        self.model_edit.setText(self._settings.get("custom_model", "") or "")
        self.embedding_model_edit.setText(self._settings.get("custom_embedding_model", "") or "")

    def _refresh_status_bar(self):
        s = db.get_llm_settings()
        model = s.get("custom_model", "") or "（未配置）"
        self.lbl_active.setText(f"OpenAI 兼容 / {model}")
        ua = s.get("updated_at", "") or "（未修改过）"
        self.lbl_updated.setText(f"上次保存: {ua}")
        try:
            st = db.get_llm_run_stats(limit=500)
            self.lbl_cost.setText(
                f"近 {st['count']} 次调用 Tokens: in={st['token_input']} / "
                f"out={st['token_output']}（成功 {st['ok']} · 失败 {st['error']} · 重试 {st['retried']}）")
        except Exception as e:  # noqa: BLE001
            self.lbl_cost.setText(f"Cost: {e}")

    # ---------- 按钮 ----------
    def _build_llmc(self) -> LLMConfig:
        """用当前表单字段构建 LLMConfig 给 probe 用。"""
        merged = dict(self._settings)
        merged.update(self._collect_fields())
        return _settings_dict_to_llmc(merged)

    def _collect_fields(self) -> dict:
        return {
            "custom_base_url": self.base_url_edit.text().strip(),
            "custom_api_key": self.api_key_edit.text().strip(),
            "custom_model": self.model_edit.text().strip(),
            "custom_embedding_model": self.embedding_model_edit.text().strip(),
        }

    def _on_test(self):
        llmc = self._build_llmc()
        self.test_btn.setEnabled(False)
        self.status_label.setText("测试中…")
        self.status_label.setStyleSheet(f"color:{T.ACCENT}")
        self._worker = ProbeWorker(llmc, timeout=5.0)
        self._worker.finished_ok.connect(self._on_test_done)
        self._worker.start()

    def _on_detect_ollama(self):
        """探测本机 Ollama：列出模型，填入 base_url + 模型名。"""
        import urllib.request, json
        host = "http://127.0.0.1:11434"
        self.ollama_btn.setEnabled(False)
        self.status_label.setText("探测 Ollama…")
        self.status_label.setStyleSheet(f"color:{T.ACCENT}")
        try:
            with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            models = [m.get("name", "") for m in data.get("models", [])]
            if not models:
                self.status_label.setText("✗ Ollama 已连接但无模型")
                self.status_label.setStyleSheet(f"color:{T.ERROR}")
                return
            # 填入 OpenAI 兼容接入地址
            self.base_url_edit.setText(f"{host}/v1")
            self.api_key_edit.setText("ollama")  # Ollama 本地无需真实 key
            # 默认选第一个模型；若当前模型在列表中则保留
            cur = self.model_edit.text().strip()
            if cur not in models:
                self.model_edit.setText(models[0])
            self.status_label.setText(f"✓ 检测到 {len(models)} 个模型")
            self.status_label.setStyleSheet(f"color:{T.SUCCESS}")
            self.models_box.setPlainText("\n".join(models))
        except Exception as e:  # noqa: BLE001
            self.status_label.setText(f"✗ 未检测到 Ollama: {str(e)[:50]}")
            self.status_label.setStyleSheet(f"color:{T.ERROR}")
            self.models_box.setPlainText("")
        finally:
            self.ollama_btn.setEnabled(True)

    def _on_test_done(self, r: dict):
        self.test_btn.setEnabled(True)
        if r.get("ok"):
            ms = r.get("latency_ms", 0)
            self.status_label.setText(f"✓ {ms} ms")
            self.status_label.setStyleSheet(f"color:{T.SUCCESS}")
            sample = r.get("models_sample") or []
            self.models_box.setPlainText("\n".join(sample) if sample else "(无可用模型)")
        else:
            err = r.get("error") or "未知错误"
            self.status_label.setText(f"✗ {err[:60]}")
            self.status_label.setStyleSheet(f"color:{T.ERROR}")
            self.models_box.setPlainText("")
        self._refresh_status_bar()

    def _on_save(self):
        fields = self._collect_fields()
        # 固定激活后端为 custom（OpenAI 兼容）
        fields["active_backend"] = "custom"
        try:
            db.set_llm_settings(**fields)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", f"{e}")
            return
        QMessageBox.information(self, "已保存", "LLM 配置已写入数据库。")
        self._refresh_status_bar()
        self.accept()


# ============== 辅助：DB dict → LLMConfig ==============
def _settings_dict_to_llmc(s: dict) -> LLMConfig:
    """合并 settings dict → LLMConfig（用于实时测速，避免依赖 DB reload）。"""
    from ..llm.settings import _settings_to_llm_config
    return _settings_to_llm_config(s)