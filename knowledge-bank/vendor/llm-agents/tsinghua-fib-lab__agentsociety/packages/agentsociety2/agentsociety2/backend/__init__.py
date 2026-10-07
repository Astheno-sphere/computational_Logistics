"""Backend API 模块 - 提供 FastAPI 后端服务。

本模块为 AI Social Scientist VSCode 扩展提供 HTTP API 服务。

路由模块
--------

- **prefill_params**: 参数预填充 API
- **experiments**: 实验管理 API
- **replay**: 回放数据 API
- **custom**: 自定义模块扫描 API
- **modules**: 模块注册 API
- **agent_skills**: Agent Skills 管理 API

启动服务::

    python -m agentsociety2.backend.app

或::

    uvicorn agentsociety2.backend.app:app --host 0.0.0.0 --port 8001
"""
