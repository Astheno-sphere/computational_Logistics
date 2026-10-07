# 安装指南

[English](installation.md) · [返回 README](../README_zh.md)

克隆仓库：

```bash
git clone https://github.com/Yinsongxu/LLM2Jev.git
cd LLM2Jev
```

在配有受支持 NVIDIA GPU 的 Linux 环境中，推荐使用 SGLang 后端；它也会安装
自身依赖的 Transformers：

```bash
uv sync --extra sglang
```

如果只需要 Transformers 后端：

```bash
uv sync --extra transformers
```

使用 pip 可编辑安装时，选择对应的 extra：

```bash
python -m pip install -e ".[sglang]"
# 或者：python -m pip install -e ".[transformers]"
```

使用 uv 安装后，激活虚拟环境：

```bash
source .venv/bin/activate
```

安装完成后，参阅[使用指南](usage_zh.md)运行 Python 示例或启动 HTTP 服务。
