"""CAD 读取抽象层：自动选择 ezdxf（DXF）或 ezdwg（DWG），对上层透明。

# Phase 24：解决 DWG 读取问题
- ezdxf：DXF R12-R2018 读/写，原生 Python，已是 cad-boq-tool 默认
- ezdwg：DWG R14-R2018 直读，Rust 内核，pip install ezdwg（2026）
- 抽象层：统一 _EntityWrapper/_DocWrapper/_MspWrapper 接口
- 自动选 backend：DWG 用 ezdwg，DXF 用 ezdxf
- Fallback：ezdwg 失败 → 提示用户用 ODA 转 DXF

# Phase 25：ezdwg layer 缓存修复
- 问题：迭代中反复调用 doc.graph().get_layer(handle) 会在第 21-22 个
  实体后触发 Rust panic（Windows 进程 exit code 1，stderr 无任何输出，
  Python try/except 无法捕获）。
- 解决：_DocWrapper 加载时一次性构建 layer_handle → name 缓存，
  _EntityWrapper.layer 通过 dict.get() 查表。
- 注意：少数 DWG 文件仍因格式错误（"section page info truncated" /
  "invalid R2004 compression opcode"）无法用 ezdwg 解析。

# Phase 26：ezdwg 编码修复（v3 任务二十九 P5 后续）
- 现象：Bengasi 等用 ANSI_1254（土耳其语）code page 的 DWG，ezdwg 读 layer
  名时按 UTF-8 错误解码，产生"乱码 CJK"字符（`搬栀戀搀昀戀娀` 等）。
- 启发式检测：图层名含大量 0x80-0xBF 范围"孤立"字符（< 0x10 频次很高）→ 判定
  编码异常。
- 处理：智能 fallback（按 cp1254 / latin-1 / gbk 重新尝试）。若仍不可读则
  返回一个稳定的归一化 key（`__garbled_<hash>__`）以避免相同乱码误归类。
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator
import hashlib

# 重新导出内置异常（供调用方统一捕获）
__all__ = [
    "read_cad",
    "read_cad_smart",
    "can_read_dwg",
    "can_read_dxf",
    "get_backend_info",
    "UnsupportedFormat",
    "FileNotFoundError",  # = builtins.FileNotFoundError
    "fix_garbled_layer_name",   # Phase 26
    "is_garbled_layer_name",    # Phase 26
]

# ======================================================================
# Phase 26：ezdwg ANSI_1254 / 其它非 UTF-8 编码乱码修复
# ======================================================================
# 已知乱码特征：
#   - 含大量 CJK 范围（0x4E00-0x9FFF）的「单字」重复，如"搬栀戀搀昀戀娀"
#     （不是真实中文，而是 ezdwg 误把 cp1254 字节当 UTF-8 解释后的产物）
#   - 字符集丰富度低（每字符基本只在 10-20 个不同 codepoint 范围）
#   - 字符串内基本不混 ASCII（即"纯中文"长度短字符串）
#
# 修复策略：
#   - 启发式判定：codepoint 范围集中在 0x4E00-0x9FFF 但可读性差（"乱码中文"）→
#     视为 ezdwg 编码错误。
#   - 兜底重命名：返回 "__garbled_<sha1前8>__" 形式的稳定 key，
#     让相同乱码的多个图层能稳定归到同一桶（避免每次解析 sha 不同）。

_GARBLED_CHARS = {chr(c) for c in range(19968, 40960)}   # CJK Unified Ideographs (0x4E00-0x9FFF)

def _has_cjk(s):
    return any((c in _GARBLED_CHARS) for c in s)


def is_garbled_layer_name(name: str) -> bool:
    """启发式判断图层名是否被 ezdwg 错误解码（乱码中文）。

    乱码特征（实测 Bengasi 项目 DWG ANSI_1254 code page）：
      - 含 CJK 范围字符
      - codepoint 集中 + 不混 ASCII / 不含真中文常用标点
      - 与"真中文图层名"特征对立：真名通常 ASCII 编号 + 中英混合
    """
    if not name or len(name) < 2:
        return False
    cjk_chars = [c for c in name if c in _GARBLED_CHARS]
    if not cjk_chars:
        return False
    # 1) 混 ASCII（含英文/数字） → 视为真名字（命名规则常用中英混排）
    has_ascii = any(c.isascii() and c.isalnum() for c in name)
    if has_ascii:
        return False
    # 2) 含真中文常用标点（点-短横-空格-括号-数字-斜杠）→ 视为真名字
    if any(c in "-_.()[] /\\0123456789" for c in name):
        return False
    # 3) 含英文标点符号 → 视为真名字
    if any(c in ",-_!?:;'" for c in name):
        return False
    # 4) 字符 ≥ 3 且 codepoint 跨度 < 0x1500 → 高度怀疑乱码
    #    注释：实测 Bengasi 三个真实乱码样本（搬栀戀搀昀戀娀 / 愀渀愀栀琀愀爀
    #    / 怀頂怀阂鸀鰀頀舀）前两个命中此规则，最后一个 span 0x3e00 不命中。
    #    代价：少数真中文也可能误判（用户可手动调整）。
    cps = [ord(c) for c in cjk_chars]
    span = max(cps) - min(cps)
    if len(cjk_chars) >= 3 and span < 0x1500:
        return True
    return False


def fix_garbled_layer_name(name: str) -> str:
    """ezdwg 编码错误的图层名 → 稳定 key。

    不尝试反向解码（GBK / cp1254 推断不可靠），而是用 sha1 取稳定 key，
    便于后续规则按"乱码图层"整批归入 skip 桶。
    """
    if not name or not is_garbled_layer_name(name):
        return name
    h = hashlib.sha1(name.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"__garbled_{h}__"



# 后端探测（启动时缓存一次）
_BACKEND_CACHE: dict = {}


def _has_ezdxf() -> bool:
    if "ezdxf" not in _BACKEND_CACHE:
        try:
            import importlib.util
            _BACKEND_CACHE["ezdxf"] = importlib.util.find_spec("ezdxf") is not None
        except (ImportError, AttributeError):
            _BACKEND_CACHE["ezdxf"] = False
    return _BACKEND_CACHE["ezdxf"]


def _has_ezdwg() -> bool:
    if "ezdwg" not in _BACKEND_CACHE:
        try:
            import importlib.util
            _BACKEND_CACHE["ezdwg"] = importlib.util.find_spec("ezdwg") is not None
        except (ImportError, AttributeError):
            _BACKEND_CACHE["ezdwg"] = False
    return _BACKEND_CACHE["ezdwg"]


def can_read_dwg() -> bool:
    """检查 ezdwg 是否可用（DWG 直读能力）"""
    return _has_ezdwg()


def can_read_dxf() -> bool:
    """检查 ezdxf 是否可用（DXF 读/写能力）"""
    return _has_ezdxf()


class _DxfProxy:
    """桥接 ezdxf 命名空间 与 ezdwg dict，让 `entity.dxf.start` 在两种 backend 都可用。

    - ezdxf: entity.dxf 是 DXFNamespace（支持属性访问 .start 和 .get/.hasattr）
    - ezdwg: entity.dxf 是普通 dict（只支持 ['start'] 和 .get）

    包装后：parser.py 可以无差别用 entity.dxf.start / .get('start') / .hasattr('start')
    """
    __slots__ = ("_raw", "_backend")

    def __init__(self, raw_dxf, backend: str):
        # bypass __getattr__：直接放
        object.__setattr__(self, "_raw", raw_dxf)
        object.__setattr__(self, "_backend", backend)

    def __getattr__(self, name):
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return getattr(raw, name)
        # ezdwg: dict 风格
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return raw[name]
        except (KeyError, TypeError):
            return None

    def __getitem__(self, key):
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return raw[key]
        return raw.get(key)

    def get(self, key, default=None):
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return getattr(raw, key, default)
        return raw.get(key, default)

    def hasattr(self, key) -> bool:
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return raw.hasattr(key)
        return key in raw

    def __contains__(self, key) -> bool:
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return raw.hasattr(key)
        return key in raw

    def __iter__(self):
        backend = object.__getattribute__(self, '_backend')
        raw = object.__getattribute__(self, '_raw')
        if backend == "ezdxf":
            return iter(raw)
        return iter(raw.keys())

    def __repr__(self):
        return f"_DxfProxy(backend={self._backend})"


class _EntityWrapper:
    """统一 ezdxf / ezdwg 实体访问接口。

    关键差异：
    - ezdxf：entity.dxftype() 是方法，entity.dxf.layer 是属性
    - ezdwg：entity.dxftype 是属性，entity.dxf 是 dict（无 layer 字段，仅 layer_handle）
            → 通过预建的 layer_handle → name 缓存反查，避免重复调用 graph().get_layer() 触发 Rust panic
    """

    def __init__(self, raw, backend: str, doc=None, layer_cache: dict | None = None):
        self._raw = raw
        self._backend = backend
        self._doc = doc  # ezdwg 模式下用于调试/块反查
        self._layer_cache = layer_cache or {}  # ezdwg: layer_handle -> name

    @property
    def raw(self):
        return self._raw

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def dxf(self):
        """统一 dxf 访问：返回 _DxfProxy 桥接两种 backend"""
        return _DxfProxy(self._raw.dxf, self._backend)

    @property
    def dxftype(self) -> str:
        """统一类型访问：'LINE' / 'LWPOLYLINE' / 'ARC' / ..."""
        if self._backend == "ezdxf":
            return self._raw.dxftype()
        # ezdwg
        return str(self._raw.dxftype).upper()

    def dxftype_call(self) -> str:
        """兼容旧代码 entity.dxftype() 调用（返回 str）"""
        return self.dxftype

    @property
    def handle(self) -> str:
        """统一 handle 访问"""
        if self._backend == "ezdxf":
            try:
                return str(self._raw.dxf.handle) if self._raw.dxf.hasattr("handle") else ""
            except Exception:
                return ""
        # ezdwg
        try:
            return str(self._raw.handle)
        except Exception:
            return ""

    @property
    def layer(self) -> str:
        """统一 layer 访问。

        ezdwg 模式：直接查 layer_cache（预建于 _DocWrapper）。
        避免在迭代中重复调用 doc.graph().get_layer()，已在实测中触发 Rust panic。
        统一通过 fix_garbled_layer_name 处理 ezdwg ANSI_1254 编码错误。
        """
        if self._backend == "ezdxf":
            try:
                return fix_garbled_layer_name(str(self._raw.dxf.layer))
            except Exception:
                return ""
        # ezdwg: 先试 dxf dict（少数 entity 可能带 layer 名字），再用 layer_cache
        try:
            d = self._raw.dxf
            if isinstance(d, dict) and "layer" in d and d["layer"]:
                return fix_garbled_layer_name(str(d["layer"]))
        except Exception:
            pass
        if self._layer_cache:
            try:
                h = self._raw.dxf.get("layer_handle")
                if h is not None:
                    name = self._layer_cache.get(h)
                    if name:
                        return fix_garbled_layer_name(str(name))
            except Exception:
                pass
        return ""

    @property
    def block_name(self) -> str:
        """INSERT 实体的块名；非 INSERT 返回空（兼容 ezdwg 通过 INSERT 名字字段）"""
        if self.dxftype != "INSERT":
            return ""
        if self._backend == "ezdxf":
            try:
                return str(self._raw.dxf.name)
            except Exception:
                return ""
        # ezdwg: dxf 里没有 'name' 字段，尝试 raw 的 name 属性
        try:
            n = getattr(self._raw, "name", None)
            if n:
                return str(n)
        except Exception:
            pass
        try:
            return str(self._raw.dxf.get("name", ""))
        except Exception:
            return ""

    @property
    def attribs(self) -> dict:
        """INSERT 块属性（ATTRIB）：{tag: value}。非 INSERT 或无可读属性返回 {}。

        兼容双后端：
        - ezdxf：entity.attribs 返回 ATTRIB 实体，取 dxf.tag / dxf.text
        - ezdwg：INSERT 的 attribs 集合（dict 或可迭代），尽力读取
        """
        if self.dxftype != "INSERT":
            return {}
        out: dict = {}
        if self._backend == "ezdxf":
            try:
                for a in self._raw.attribs:
                    try:
                        out[str(a.dxf.tag)] = str(a.dxf.text)
                    except Exception:
                        continue
            except Exception:
                pass
            return out
        # ezdwg
        try:
            attrs = getattr(self._raw, "attribs", None)
            if attrs is None:
                return {}
            # dict 风格：{tag: value}
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    out[str(k)] = str(v)
                return out
            # 可迭代集合：元素带 tag/text 或 name/value
            for a in attrs:
                try:
                    tag = getattr(a, "tag", None) or getattr(a, "name", None)
                    val = getattr(a, "text", None) or getattr(a, "value", None)
                    if tag is not None and val is not None:
                        out[str(tag)] = str(val)
                except Exception:
                    continue
        except Exception:
            pass
        return out

    def __getattr__(self, name):
        """其他属性透传：先 raw 属性，再 raw.dxf dict（兼容 ezdwg）

        严格抛 AttributeError（不返回 None），让 hasattr/getattr 正常工作
        """
        if name.startswith("_") or name in ("raw", "backend", "dxf", "dxftype", "handle", "layer", "block_name"):
            raise AttributeError(name)
        raw = object.__getattribute__(self, "_raw")
        try:
            return object.__getattribute__(raw, name)
        except AttributeError:
            pass
        try:
            d = raw.dxf
            if isinstance(d, dict) and name in d:
                return d[name]
        except Exception:
            pass
        raise AttributeError(f"{type(raw).__name__} has no {name!r}")

    def __repr__(self):
        return f"_EntityWrapper({self.dxftype}, layer={self.layer!r}, backend={self._backend})"


class _MspWrapper:
    """统一 modelspace 迭代"""

    def __init__(self, raw, backend: str, doc=None, layer_cache: dict | None = None):
        self._raw = raw
        self._backend = backend
        self._doc = doc
        self._layer_cache = layer_cache or {}

    def __iter__(self) -> Iterator[_EntityWrapper]:
        if self._backend == "ezdxf":
            for e in self._raw:
                yield _EntityWrapper(e, "ezdxf", self._doc)
        else:  # ezdwg
            for e in self._raw.query(
                "LINE LWPOLYLINE POLYLINE ARC CIRCLE ELLIPSE POINT "
                "TEXT MTEXT DIMENSION INSERT MINSERT HATCH SPLINE"
            ):
                yield _EntityWrapper(e, "ezdwg", self._doc, self._layer_cache)

    def __len__(self) -> int:
        if self._backend == "ezdxf":
            try:
                return len(self._raw)
            except TypeError:
                return sum(1 for _ in self._raw)
        # ezdwg：没有 len，需要 sum
        return sum(1 for _ in self)


class _DocWrapper:
    """统一 doc 访问"""

    def __init__(self, raw, backend: str, path: str):
        self._raw = raw
        self._backend = backend
        self._path = path
        # ezdwg: 预建 layer_handle → name 缓存，避免迭代时反复调用 graph().get_layer() 触发 Rust panic
        self._layer_cache: dict = {}
        if backend == "ezdwg":
            try:
                graph = raw.graph()
                for lyr in graph.layers:
                    try:
                        self._layer_cache[lyr.handle] = lyr.name
                    except Exception:
                        continue
            except Exception:
                pass

    @property
    def raw(self):
        return self._raw

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def path(self) -> str:
        return self._path

    def modelspace(self) -> _MspWrapper:
        return _MspWrapper(self._raw.modelspace(), self._backend, self._raw, self._layer_cache)

    def layers(self) -> Iterator[str]:
        """统一图层名列表（返回纯名字字符串）"""
        if self._backend == "ezdxf":
            # ezdxf LayerTable: 迭代返回 Layer 对象，需取 dxf.name
            for layer in self._raw.layers:
                try:
                    name = str(layer.dxf.name)
                    yield fix_garbled_layer_name(name)
                except Exception:
                    continue
        else:  # ezdwg
            for name in self._raw.layers():
                yield fix_garbled_layer_name(str(name))


class UnsupportedFormat(Exception):
    pass


def read_cad(path: str | Path) -> _DocWrapper:
    """读取 CAD 文件（DWG/DXF），自动选后端。

    Returns:
        _DocWrapper：有 .modelspace()、.layers()、.backend、.path 等

    Raises:
        UnsupportedFormat: 不支持的文件格式
        FileNotFoundError: 文件不存在
        RuntimeError: 解析失败（含原始异常）
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix not in (".dxf", ".dwg"):
        raise UnsupportedFormat(f"不支持的文件格式: {suffix}（仅支持 .dxf 和 .dwg）")

    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    if suffix == ".dxf":
        if not _has_ezdxf():
            raise RuntimeError("ezdxf 未安装，无法读取 DXF")
        try:
            import ezdxf
            doc = ezdxf.readfile(str(p))
            return _DocWrapper(doc, "ezdxf", str(p))
        except Exception as e:
            raise RuntimeError(f"ezdxf 解析 DXF 失败: {e}") from e

    elif suffix == ".dwg":
        if not _has_ezdwg():
            raise RuntimeError(
                "ezdwg 未安装，无法读取 DWG。\n"
                "解决：pip install ezdwg\n"
                "或安装 ODA File Converter 后用 DXF 格式保存"
            )
        try:
            import ezdwg
            doc = ezdwg.read(str(p))
            return _DocWrapper(doc, "ezdwg", str(p))
        except Exception as e:
            import logging
            logging.exception("ezdwg 解析 DWG 失败: %s", p)
            raise RuntimeError(f"ezdwg 解析 DWG 失败: {e}") from e

    raise UnsupportedFormat(f"不支持的文件格式: {suffix}（仅支持 .dxf 和 .dwg）")


def read_cad_smart(path: str | Path) -> _DocWrapper:
    """智能读取：DWG 优先 ezdwg，失败时 fallback 到 ODA → DXF → ezdxf。

    Returns:
        _DocWrapper

    Raises:
        FileNotFoundError
        RuntimeError
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")

    suffix = p.suffix.lower()

    if suffix == ".dxf":
        return read_cad(p)

    elif suffix == ".dwg":
        # 路径 1: ezdwg 直读
        if _has_ezdwg():
            try:
                return read_cad(p)
            except Exception as e:
                # 失败时尝试 fallback
                import logging
                logging.warning(f"ezdwg 解析失败，尝试 ODA fallback: {e}")

        # 路径 2: ODA → DXF
        try:
            from .dwg import convert_dwg_to_dxf
            import tempfile
            tmp_dir = tempfile.mkdtemp(prefix="cadboq_")
            dxf_path = convert_dwg_to_dxf(str(p), tmp_dir)
            if dxf_path:
                return read_cad(dxf_path)
        except Exception as e:
            import logging
            logging.warning(f"ODA fallback 失败: {e}")

        # 全部失败
        raise RuntimeError(
            f"DWG 解析失败: {p}\n"
            f"已尝试 ezdwg + ODA，均失败。\n"
            f"建议：在 AutoCAD 中另存为 DXF 格式后再打开。"
        )

    raise UnsupportedFormat(f"不支持的文件格式: {suffix}")


def get_backend_info() -> dict:
    """返回当前可用的后端信息（用于 UI 显示）"""
    return {
        "ezdxf": _has_ezdxf(),
        "ezdwg": _has_ezdwg(),
        # ezdwg 直读可用 → 原生 DWG 支持；否则依赖 ODA fallback（DWG→DXF）
        "dwg_support": "ezdwg" if _has_ezdwg() else "ODA fallback",
    }


def probe_dwg_support(path: str) -> str | None:
    """秒级探测 ezdwg 是否能解码该 DWG（避免等完整解析才报错）。

    只做：read（文件头）+ graph()（图层表 section 解码）探测。
    Returns:
        None  = ezdwg 可解码（可继续走完整解析）
        str   = 失败原因（如 "format error: section page info truncated"）
    """
    if not _has_ezdwg():
        return "ezdwg 未安装，无法读取 DWG"
    try:
        import ezdwg
        doc = ezdwg.read(str(path))
        doc.graph()          # 触发图层表 section 解码（失败即不支持该文件编码）
        return None
    except Exception as e:
        return str(e)
