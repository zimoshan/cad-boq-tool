# =============================================================================
# cad-boq-tool webapi 容器镜像
# 基镜像：python:3.12-slim（ezdwg Rust 核心兼容，体积小）
# 多阶段构建：builder 安装依赖；runtime 拷贝 site-packages
# =============================================================================

# ---------- 阶段 1：builder ----------
FROM python:3.12-slim AS builder

# 系统依赖（ezdxf/ezdwg 编译期需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# 拷贝依赖清单
COPY requirements.txt /tmp/requirements.txt

# 安装 Python 依赖到独立路径（供 runtime 拷贝）
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# ---------- 阶段 2：runtime ----------
FROM python:3.12-slim

# 运行时系统依赖（ezdxf/ezdwg runtime 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    libffi8 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash cadboq

# 拷贝 Python 依赖
COPY --from=builder /install /usr/local

# 工作目录
WORKDIR /app

# 拷贝应用代码
COPY app/ /app/app/
COPY webapi/ /app/webapi/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY env.example /app/env.example

# 创建日志/数据目录
RUN mkdir -p /var/log/cad-boq /var/lib/cad-boq && \
    chown -R cadboq:cadboq /var/log/cad-boq /var/lib/cad-boq /app

USER cadboq

# 健康检查（uvicorn /health 端点）
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8521/health || exit 1

# 暴露端口
EXPOSE 8521

# 启动
CMD ["uvicorn", "webapi.main:app", "--host", "0.0.0.0", "--port", "8521"]
