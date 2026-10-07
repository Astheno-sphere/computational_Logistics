命令行界面
========================================

AgentSociety 2 提供了一个强大的命令行界面（CLI）用于运行实验。

概述
------------

CLI 是运行 AgentSociety 2 实验的主要方式。它提供：

* 实验配置加载和验证
* 步骤化执行跟踪
* 进度持久化（pid.json）
* 灵活的日志配置
* 后台运行支持

基本用法
------------

.. code-block:: bash

   python -m agentsociety2.society.cli [OPTIONS]

必需参数
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 参数
     - 说明
   * - ``--config`` <PATH>
     - 初始化配置文件路径（init_config.json）
   * - ``--steps`` <PATH>
     - 步骤配置文件路径（steps.yaml）

可选参数
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 参数
     - 默认值
     - 说明
   * - ``--run-dir`` <PATH>
     - 当前目录
     - 运行输出目录路径
   * - ``--experiment-id`` <TEXT>
     - 无
     - 实验标识符
   * - ``--log-level``
     - INFO
     - 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
   * - ``--log-file`` <PATH>
     - 无
     - 日志文件路径（**后台运行必需**）
   * - ``--batch-size`` <INT>
     - ``AGENTSOCIETY_BATCH_SIZE`` 或 256
     - 每个 ``step_agent_batch`` Ray Task 处理的 agent 数
   * - ``--replay-disable``
     - false
     - 禁用回放写入（百万级 agent 场景适用）
   * - ``--resume``
     - false
     - 从 ``run_dir/SOCIETY.json`` 和 ``SOCIETY_STEP.json`` 恢复中断的实验。CLI 会恢复
       society 的时钟、步数和各 env 模块状态，并跳过已经完成的 ``RunStep``。``Ask``、
       ``Intervene`` 和 ``Questionnaire`` 会重新执行，产物时间戳也会随之更新；如果
       ``steps.yaml`` 与 checkpoint 不一致，CLI 会给出告警。

运行实验
------------

前台运行（调试模式）
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m agentsociety2.society.cli \
       --config hypothesis_1/experiment_1/init/init_config.json \
       --steps hypothesis_1/experiment_1/init/steps.yaml \
       --run-dir hypothesis_1/experiment_1/run \
       --log-level DEBUG

日志输出到控制台。

后台运行（生产模式）
~~~~~~~~~~~~~~~~~~~~~~~~~~

**重要**: 后台运行时必须指定 ``--log-file`` 以捕获日志。

.. code-block:: bash

   python -m agentsociety2.society.cli \
       --config hypothesis_1/experiment_1/init/init_config.json \
       --steps hypothesis_1/experiment_1/init/steps.yaml \
       --run-dir hypothesis_1/experiment_1/run \
       --experiment-id "1_1" \
       --log-level INFO \
       --log-file hypothesis_1/experiment_1/run/output.log &

检查实验状态
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # 检查 pid.json 查看运行状态
   cat hypothesis_1/experiment_1/run/pid.json

   # 查看日志
   tail -f hypothesis_1/experiment_1/run/output.log

停止实验
~~~~~~~~~~~~~

.. code-block:: bash

   # 查找进程 ID
   pid=$(jq -r '.pid' hypothesis_1/experiment_1/run/pid.json)

   # 发送 SIGTERM 信号
   kill $pid

恢复中断的实验
~~~~~~~~~~~~~~~~~~~~~

实验会在每步结束时原子地写出 checkpoint。即使进程在写入过程中崩溃，已有 checkpoint 也不会被破坏：

* ``run_dir/SOCIETY.json`` —— 初始化时写一次，保存不可变的全量配置，例如 ``agent_specs``、
  env 模块类型和 kwargs、``batch_size``、``steps_hash``。
* ``run_dir/SOCIETY_STEP.json`` —— 每步标量：当前时间、步数、已完成的顶层步数、``terminated``。
* 各 env 模块的状态写到 ``run_dir/env/{module_type}/state/ENV_STATE.json``，具体格式由模块自定。

用 ``--resume`` 从最后完成的步续跑：

.. code-block:: bash

   python -m agentsociety2.society.cli \
       --config hypothesis_1/experiment_1/init/init_config.json \
       --steps hypothesis_1/experiment_1/init/steps.yaml \
       --run-dir hypothesis_1/experiment_1/run \
       --resume \
       --log-file hypothesis_1/experiment_1/run/output.log &

恢复时以 checkpoint 中的 env 模块类型和 kwargs、时钟、步数为准，而不是重新读取 config 文件中的
这些值，这可以避免配置漂移。``RunStep`` 会根据游标跳过已完成的部分；``Ask``、``Intervene`` 和
``Questionnaire`` 会重新执行。如果 ``steps.yaml`` 的 hash 与 checkpoint 不一致，CLI 会输出
WARNING。可以用下面的命令校验恢复点：

.. code-block:: bash

   cat hypothesis_1/experiment_1/run/SOCIETY_STEP.json   # step_count / completed_step_count

.. note::

   只有覆盖了 ``to_workspace()`` 和 ``restore()`` 的 env 模块才能在 resume 时恢复动态状态
   （见 :doc:`env_modules`）。未覆盖的模块 resume 后会回到 fresh 态。

配置文件
------------

init_config.json
~~~~~~~~~~~~~~~~~~~~

初始化配置文件定义实验的基本设置：

.. code-block:: json

   {
       "agents": [
           {
               "agent_id": 1,
               "agent_type": "PersonAgent",
               "kwargs": {
                   "id": 1,
                   "name": "Alice",
                   "personality": "friendly"
               }
           }
       ],
       "env_modules": [
           {
               "module_type": "SimpleSocialSpace",
               "kwargs": {
                   "agent_id_name_pairs": [[1, "Alice"]]
               }
           }
       ],
       "codegen_router": {
           "final_summary_enabled": true
       }
   }

steps.yaml
~~~~~~~~~~~~~

步骤配置文件定义实验的执行步骤：

.. code-block:: yaml

   start_t: "2026-01-01T00:00:00"
   steps:
     - type: ask
       question: "Introduce yourself to the group"

     - type: run
       num_steps: 1
       tick: 3600

     - type: intervene
       instruction: "Make everyone feel better"

步骤类型
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 类型
     - 说明
   * - ``ask``
     - 只读查询，不修改环境
   * - ``intervene``
     - 读写操作，可以修改环境
   * - ``step``
     - 执行一个模拟步骤（指定 tick 时长）

输出文件
------------

运行实验后，``run-dir`` 目录将包含：

.. code-block:: text

   hypothesis_1/experiment_1/run/
   ├── pid.json              # 进程信息（PID、启动时间、状态）
   ├── output.log            # 日志文件（如果指定了 --log-file）
   ├── replay/               # _schema.json + sharded JSONL replay datasets
   ├── trace/                # sharded JSONL trace spans
   ├── agents/               # agent workspaces
   └── artifacts/            # 步骤产物（如果启用了 save_artifact）
       ├── step_1_ask.json
       ├── step_2_intervene.json
       └── ...

pid.json 格式
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
       "pid": 12345,
       "start_time": "2026-03-20T10:30:00",
       "status": "running",
       "config": {
           "config_path": "/path/to/init_config.json",
           "steps_path": "/path/to/steps.yaml"
       }
   }

日志级别
------------

可选的日志级别：

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - 级别
     - 用途
   * - ``DEBUG``
     - 详细的调试信息，包括 LLM 调用
   * - ``INFO``
     - 常规运行信息（默认）
   * - ``WARNING``
     - 警告信息
   * - ``ERROR``
     - 错误信息
   * - ``CRITICAL``
     - 严重错误

示例：完整工作流
------------------------

.. code-block:: bash

   # 1. 准备配置文件
   mkdir -p my_experiment/init my_experiment/run
   # ... 创建 init_config.json 和 steps.yaml ...

   # 2. 前台测试运行
   python -m agentsociety2.society.cli \
       --config my_experiment/init/init_config.json \
       --steps my_experiment/init/steps.yaml \
       --run-dir my_experiment/run \
       --log-level DEBUG

   # 3. 后台生产运行
   python -m agentsociety2.society.cli \
       --config my_experiment/init/init_config.json \
       --steps my_experiment/init/steps.yaml \
       --run-dir my_experiment/run \
       --experiment-id "exp_001" \
       --log-level INFO \
       --log-file my_experiment/run/output.log &

   # 4. 监控运行
   tail -f my_experiment/run/output.log

   # 5. 完成后检查 replay catalog
   python - <<'PY'
   from agentsociety2.storage import ReplayReader
   reader = ReplayReader("my_experiment/run/replay")
   print([d["dataset_id"] for d in reader.load_dataset_catalog()])
   reader.close()
   PY
