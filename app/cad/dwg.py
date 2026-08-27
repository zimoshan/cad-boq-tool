"""DWG → DXF 转换（ODA File Converter CLI 封装）"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..config import ODA_INSTALL_HINTS


def find_oda_converter() -> str | None:
    """定位 ODAFileConverter.exe

    优先级：ODA_FILE_CONVERTER 环境变量 > PATH > 常见安装目录。
    常见目录兼容三种布局：
      - 直接 exe：<base>/ODAFileConverter.exe
      - 版本子目录：<base>/ODAFileConverter 27.1.0/ODAFileConverter.exe
      - 旧式含版本子目录：<base>/ODAFileConverter/<ver>/ODAFileConverter.exe
    """
    # 1) 环境变量显式指定（指向 exe 或其所在目录均可）
    env = os.environ.get("ODA_FILE_CONVERTER", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return str(p)
        if p.is_dir():
            cand = p / "ODAFileConverter.exe"
            if cand.exists():
                return str(cand)

    # 2) PATH
    name = "ODAFileConverter.exe"
    found = shutil.which(name)
    if found:
        return found

    # 3) 常见安装目录（ODA_INSTALL_HINTS 已是父目录，如 C:\Program Files\ODA）
    hints = list(ODA_INSTALL_HINTS) + [
        str(Path.home() / "AppData" / "Local" / "Programs" / "ODA"),
        str(Path.home() / "AppData" / "Local" / "Programs" / "ODA" / "ODAFileConverter"),
    ]
    for base in hints:
        p = Path(base)
        if not p.is_dir():
            continue
        # 直接 exe
        direct = p / name
        if direct.exists():
            return str(direct)
        # 版本子目录：ODAFileConverter 27.1.0/ODAFileConverter.exe
        for cand in sorted(p.glob(f"{name}*/{name}"), reverse=True):
            if cand.exists():
                return str(cand)
        # 旧式：<base>/ODAFileConverter/<ver>/ODAFileConverter.exe
        for cand in sorted(p.glob(f"*/{name}"), reverse=True):
            if cand.exists():
                return str(cand)
    return None


def convert_dwg_to_dxf(dwg_path: str, out_dir: str, version: str = "ACAD2018") -> str | None:
    """DWG → DXF。返回输出 DXF 路径；失败返回 None。

    ODAFileConverter 的输入是「目录」，会把目录下全部 DWG 都转换——
    因此把源文件复制到独立工作目录，只转换目标文件（避免同目录其他图被连带转换）。
    """
    exe = find_oda_converter()
    if not exe:
        return None
    dwg = Path(dwg_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 独立工作目录（只含目标文件）
    import shutil
    import uuid
    work = out / f"_work_{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(dwg, work / dwg.name)
        # ODAFileConverter.exe <in_dir> <out_dir> <version> <type> <recurse> <audit>
        proc = subprocess.run(
            [exe, str(work), str(out), version, "DXF", "0", "1"],
            capture_output=True, text=True, timeout=300,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    target = out / (dwg.stem + ".dxf")
    # 失败时用 returncode / stderr 给出精确诊断，避免静默吞错
    if not target.exists():
        raise RuntimeError(
            f"ODA 转换失败（退出码 {proc.returncode}），未生成 DXF: {target}\n"
            f"命令: {exe} {dwg.parent} {out} {version} DXF 0 1\n"
            f"stdout: {proc.stdout.strip()}\n"
            f"stderr: {proc.stderr.strip()}"
        )
    if proc.returncode != 0:
        import logging
        logging.warning(
            f"ODA 转换退出码 {proc.returncode} 但已生成 DXF，忽略: {target}"
        )
    return str(target)


def convert_dwgs_batch(dwg_paths: list, out_dir: str, parallel: int = 4,
                       version: str = "ACAD2018") -> dict:
    """批量 DWG → DXF（多 ODA 实例并行，每个实例一次启动转一组）。

    ODAFileConverter 的输入是目录（目录内全部 DWG 一起转换），因此把
    dwg_paths 分成 parallel 组，每组复制到一个工作子目录，并行启动
    parallel 个 ODAFileConverter 实例。消除「每张图一次启动」的开销。

    注意：同组内文件名不能冲突（转换后同名会互相覆盖）——按 stem 分组
    预先保证唯一；重名文件会被分到不同组。

    Returns:
        {dwg_path: dxf_path} 成功转换的映射（失败的不在结果里）
    """
    import tempfile

    exe = find_oda_converter()
    if not exe or not dwg_paths:
        return {}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 负载均衡分组（按文件大小贪心，大文件优先放最小组）；
    # 同 stem 重名文件分到不同组，避免同目录转换互相覆盖
    n_groups = max(1, min(parallel, len(dwg_paths)))
    flat = sorted((Path(p) for p in dwg_paths),
                  key=lambda p: -p.stat().st_size if p.exists() else 0)
    sizes = [0] * n_groups
    groups = [[] for _ in range(n_groups)]
    stem_last = {}
    for p in flat:
        stem = p.stem
        # 同 stem 已在组 gi，重名文件需避开该组
        banned = stem_last.get(stem)
        cands = [i for i in range(len(groups)) if i != banned] or list(range(len(groups)))
        gi = min(cands, key=lambda i: sizes[i])
        groups[gi].append(p)
        sizes[gi] += p.stat().st_size if p.exists() else 0
        stem_last[stem] = gi

    work_root = Path(tempfile.mkdtemp(prefix="cadboq_bodabatch_"))
    try:
        from concurrent.futures import ThreadPoolExecutor

        def _convert_group(gi: int, files: list) -> list:
            """转换一组文件：复制到独立工作目录 → 一次 ODA 启动 → 收集结果"""
            if not files:
                return []
            work = work_root / f"g{gi}"
            out_sub = out / f"g{gi}"
            work.mkdir(parents=True, exist_ok=True)
            out_sub.mkdir(parents=True, exist_ok=True)
            for f in files:
                try:
                    shutil.copy2(f, work / f.name)
                except OSError:
                    continue
            try:
                subprocess.run(
                    [exe, str(work), str(out_sub), version, "DXF", "0", "1"],
                    capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                pass
            results = []
            for f in files:
                dxf = out_sub / (f.stem + ".dxf")
                if dxf.exists() and dxf.stat().st_size > 0:
                    results.append((str(f), str(dxf)))
            return results

        all_pairs = []
        with ThreadPoolExecutor(max_workers=len(groups)) as tp:
            for pairs in tp.map(_convert_group, range(len(groups)), groups):
                all_pairs.extend(pairs)
        return dict(all_pairs)
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
