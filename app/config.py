"""全局配置"""
import os
from pathlib import Path

APP_NAME = "图纸算量工具"
VERSION = "0.1.0"

# 数据目录（SQLite 数据库与项目文件）
DATA_DIR = Path.home() / ".cad-boq-tool"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "projects.db"

# 日志目录（RotatingFileHandler，默认 5MB×3）
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

# 大图模式阈值：实体数超过则只渲染可见图层
BIG_DRAWING_THRESHOLD = 50_000

# 解析缓存容量上限（P2-5：parse_cache 硬编码 100 → 配置化；可用环境变量覆盖）
PARSE_CACHE_MAX_ENTRIES = int(os.environ.get("CAD_BOQ_PARSE_CACHE_MAX", "100"))

# DWG 转换（ODA 探测：父目录 + 任意 "ODAFileConverter*" 版本子目录）
ODA_INSTALL_HINTS = [
    r"C:\Program Files\ODA",
    r"C:\Program Files (x86)\ODA",
    r"D:\Program Files\ODA",
    r"D:\Program Files (x86)\ODA",
]

# BOQ 表头候选（用于自动探测；支持中文）
BOQ_HEADER_CANDIDATES = {
    "code": ["编号", "序号", "item no", "item no.", "code", "no", "no.", "item code"],
    "description": ["描述", "项目名称", "名称", "工作内容", "description", "item description", "title", "name"],
    "unit": ["单位", "unit", "uom"],
    "original_qty": ["数量", "工程量", "qty", "quantity", "original qty"],
}

# 默认比例（图纸单位 → 实际单位；mm→m 为 0.001）
DEFAULT_SCALE_FACTOR = 1.0

# ---- V2：LLM 配置（任务二十二，模型从业务逻辑抽离）----
MODEL_PROVIDER = "custom"            # 固定 custom（OpenAI 兼容协议）
MODEL_NAME = ""                      # 主模型（分类/绑定重排序，从 LLM 设置读取）
EMBEDDING_MODEL = ""                 # embedding 模型（从 LLM 设置读取）
LLM_TEMPERATURE = 0.1
LLM_TIMEOUT = 120
LLM_MAX_TOKENS = 4000
# 提示词版本号：改 prompts.py 的绑定 Prompt 时递增（写入 llm_run 审计）
BINDING_PROMPT_VERSION = "binding-v3"   # v3: 判定规则/字段含义/示例明确化（2026-08-27）
CLASSIFY_PROMPT_VERSION = "classify-v1"
# 绑定候选召回参数
BINDING_TOP_N = 5                    # 规则/LLM 候选上限
EMBEDDING_TOP_N = 15                 # embedding 语义召回 Top-N（混合召回扩大召回，LLM 再压缩到 BINDING_TOP_N）

# P2-2：LLM 精排并发（候选生成多 EO 并行调 LLM；仍逐 EO 写 llm_run 审计）
LLM_BATCH_WORKERS = 2
