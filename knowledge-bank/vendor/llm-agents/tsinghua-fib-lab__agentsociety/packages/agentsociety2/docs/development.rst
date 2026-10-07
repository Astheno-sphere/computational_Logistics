开发指南
=================

本指南面向 AgentSociety 2 的贡献者。

设置开发环境
-----------------------------------

1. Fork 并克隆仓库：

.. code-block:: bash

   git clone https://github.com/your-username/agentsociety.git
   cd agentsociety

2. 以开发模式安装：

.. code-block:: bash

   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e "packages/agentsociety2[dev]"

3. 安装 pre-commit hooks：

.. code-block:: bash

   cd packages/agentsociety2
   pre-commit install

运行测试
-------------

.. code-block:: bash

   cd packages/agentsociety2
   pytest

使用覆盖率：

.. code-block:: bash

   pytest --cov=agentsociety2 --cov-report=html

代码风格
----------

AgentSociety 2 使用 `ruff`_ 进行检查和格式化：

.. code-block:: bash

   # Check code
   ruff check .

   # Format code
   ruff format .

我们还使用 `mypy`_ 进行类型检查：

.. code-block:: bash

   mypy agentsociety2/

.. _ruff: https://github.com/astral-sh/ruff
.. _mypy: https://github.com/python/mypy

项目结构
-----------------

.. code-block:: text

   agentsociety2/
   ├── agent/           # Agent implementations
   ├── backend/         # FastAPI backend service (REST API)
   ├── config/          # Configuration and LLM routing
   ├── contrib/         # Contributed agents and environments
   ├── custom/          # Custom module templates
   ├── env/             # Environment modules and routers
   ├── logger/          # Enhanced logging with file support
   ├── registry/        # Module registry for custom components
   ├── skills/          # Research skills (literature, experiment, hypothesis, etc.)
   ├── society/         # Society helper utilities and CLI
   ├── storage/         # Replay storage system
   └── trace/           # Distributed trace span writers

研究技能模块
-------------------------

``skills/`` 模块提供 LLM 原生的研究工作流：

* **literature**: 学术文献搜索和管理
* **experiment**: 实验配置和执行
* **hypothesis**: 假设生成和管理
* **analysis**: 数据分析和报告

后端 API
-------------------------

``backend/`` 模块提供 FastAPI REST API：

* **Routers**:
  * ``/api/v1/prefill-params`` - 模块参数预填充信息
  * ``/api/v1/experiments`` - 实验管理
  * ``GET /api/v1/experiments/{h}/{e}/log`` - 日志尾部读取（查询参数 ``tail``、``source``；``source`` 可为 ``auto``、``output.log`` 或 ``stderr.log``；默认约 2000 行）
  * ``/api/v1/modules`` - 模块管理
  * ``/api/v1/replay`` - 回放数据访问
  * ``/api/v1/custom`` - 自定义模块注册
  * ``/api/v1/agent-skills`` - Agent Skills 扫描、导入和热重载

* **Service Layer**: 业务逻辑层

启动后端：

.. code-block:: bash

   python -m agentsociety2.backend.run

   # 访问 http://localhost:8001/docs 查看 API 文档

日志系统
-------------------------

增强的日志系统支持：

* **彩色控制台输出**: 按日志级别着色
* **文件日志**: 使用 ``add_file_handler()`` 写入日志文件
* **LiteLLM 集成**: 自定义回调日志记录 LLM 调用

.. code-block:: python

   from agentsociety2.logger import get_logger, set_logger_level, add_file_handler

   # 设置日志级别
   set_logger_level("DEBUG")

   # 添加文件处理器
   add_file_handler("output.log", level="INFO")

   logger = get_logger()
   logger.info("Hello, AgentSociety!")

贡献
------------

请参阅 :doc:`contributing` 了解贡献指南。

构建文档
----------------------

.. code-block:: bash

   cd packages/agentsociety2/docs
   make html

构建的文档将位于 ``_build/html/``。

要在编辑时进行实时预览：

.. code-block:: bash

   make livehtml

发布流程
---------------

1. 更新 ``pyproject.toml`` 中的版本
2. 更新 ``CHANGELOG.md``
3. 提交更改
4. 创建标签：``git tag agentsociety2-vX.Y.Z``
5. 推送：``git push --tags``
6. GitHub Actions 将构建并发布到 PyPI
