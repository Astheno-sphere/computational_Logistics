# 数据分析

AgentSociety提供了完整的数据存储能力，所有实验数据都被持久化到数据库中以支持后续的数据分析工作。
本文档介绍如何从SQLite数据库中提取实验数据并转换为pandas DataFrame进行数据分析。

---

AgentSociety将实验数据存储在SQLite数据库中（默认路径：`./agentsociety_data/sqlite.db`）。

## 表结构

数据库中包含以下表：

### 实验表 (as_experiment)

存储实验的基本信息和元数据：
- `tenant_id`: 租户ID
- `id`: 实验UUID
- `name`: 实验名称
- `num_day`: 实验总天数
- `status`: 实验状态，0表示实验准备中，1表示实验运行中，2表示实验已完成，3表示实验出错
- `cur_day`: 当前天数
- `cur_t`: 当前时刻（单位：秒），与`cur_day`字段共同确定模拟中的时间
- `config`: 实验配置（JSON格式）
- `error`: 错误信息
- `input_tokens`: 输入token数量
- `output_tokens`: 输出token数量
- `created_at`: 创建时间
- `updated_at`: 更新时间

实验表的主要用途是帮助用户找到待分析的实验的ID，以便查找数据表。

### 动态生成的实验数据表
每个实验会生成一组以实验ID命名的数据表：

```{admonition} 表名规则
:class: tip

实验ID的UUID格式为`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`，其中`x`为十六进制数字。
在数据库中，实验ID的UUID格式会被转换为`xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx`的格式，以便符合SQLite的表名规则。
```

1. **智能体画像表** (`as_{exp_id}_agent_profile`)
   - `id`: 智能体ID
   - `name`: 智能体名称
   - `profile`: 智能体画像信息（JSON格式）

2. **智能体状态表** (`as_{exp_id}_agent_status`)
   - `id`: 智能体ID
   - `day`: 实验天数
   - `t`: 模拟时刻（单位：秒），与`day`字段共同确定模拟中的时间
   - `lng`: 经度
   - `lat`: 纬度
   - `parent_id`: 所在的车道、人行道或AOI的ID
   - `action`: 当前行为
   - `status`: 状态信息（JSON格式）
   - `created_at`: 记录创建时间

3. **对话记录表** (`as_{exp_id}_agent_dialog`)
   - `id`: 智能体ID
   - `day`: 实验天数
   - `t`: 模拟时刻（单位：秒），与`day`字段共同确定模拟中的时间
   - `type`: 对话类型，0表示内心想法、1表示与其他智能体对话、2表示与用户对话
   - `speaker`: 对话对象ID，不为空表示对话内容是其他智能体所说，否则是该智能体所说
   - `content`: 对话内容
   - `created_at`: 记录创建时间

4. **问卷结果表** (`as_{exp_id}_agent_survey`)
   - `id`: 智能体ID
   - `day`: 实验天数
   - `t`: 模拟时刻（单位：秒），与`day`字段共同确定模拟中的时间
   - `survey_id`: 问卷ID
   - `result`: 问卷结果（JSON格式）
   - `created_at`: 记录创建时间

5. **全局提示表** (`as_{exp_id}_global_prompt`)
   - `day`: 实验天数
   - `t`: 模拟时刻（单位：秒），与`day`字段共同确定模拟中的时间
   - `prompt`: 提示内容
   - `created_at`: 记录创建时间

6. **指标表** (`as_{exp_id}_metric`)
   - `id`: 记录ID
   - `key`: 指标名称
   - `value`: 指标值
   - `step`: 指标步数
   - `created_at`: 记录创建时间

## 数据库访问

这里演示使用[duckdb](https://duckdb.org/)连接数据库并读取实验数据。
实际使用中也可以使用其他数据库连接工具，如sqlite3、psycopg2等。

```{admonition} 安装duckdb
:class: tip

使用`pip install duckdb`即可安装duckdb

```

### 读取实验表获取实验ID

首先需要连接数据库并查询可用的实验。导入必要的库：

```python
import duckdb
import pandas as pd
import uuid
from datetime import datetime
```

连接到SQLite数据库：

```python
db_path = "./agentsociety_data/sqlite.db"
conn = duckdb.connect()
conn.execute(f"ATTACH '{db_path}' AS agentsociety (TYPE sqlite)")
```

定义查询所有实验信息的函数：

```python
def get_experiments():
    query = """
    SELECT 
        tenant_id,
        id,
        name,
        num_day,
        status,
        cur_day,
        cur_t,
        created_at,
        updated_at,
        input_tokens,
        output_tokens
    FROM agentsociety.as_experiment
    ORDER BY created_at DESC
    """
    
    df_experiments = conn.execute(query).df()
    return df_experiments
```

获取实验列表并选择要分析的实验：

```python
experiments_df = get_experiments()
print("Available experiments:")
print(experiments_df[['id', 'name', 'status', 'created_at']])

exp_id = experiments_df.iloc[0]['id']
print(f"Selected experiment: {exp_id}")
```

### 根据实验ID读取模拟结果数据

获得实验ID后，可以读取该实验的所有相关数据表。
首先定义数据提取函数，注意需要将UUID中的连字符替换为下划线以匹配表名规则：

```python
def get_experiment_data(exp_id):
    table_suffix = str(exp_id).replace('-', '_')
    data = {}
    
    # TODO

    return data
```

其中`TODO`的部分如下：

1. **读取智能体画像数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_agent_profile
    """
    data['profiles'] = conn.execute(query).df()
    print(f"Agent profiles: {len(data['profiles'])} records")
except Exception as e:
    print(f"Failed to read agent profiles: {e}")
    data['profiles'] = pd.DataFrame()
```

2. **读取智能体状态数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_agent_status
    ORDER BY day, t
    """
    data['statuses'] = conn.execute(query).df()
    print(f"Agent statuses: {len(data['statuses'])} records")
except Exception as e:
    print(f"Failed to read agent statuses: {e}")
    data['statuses'] = pd.DataFrame()
```

3. **读取对话记录数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_agent_dialog
    ORDER BY day, t
    """
    data['dialogs'] = conn.execute(query).df()
    print(f"Dialog records: {len(data['dialogs'])} records")
except Exception as e:
    print(f"Failed to read dialogs: {e}")
    data['dialogs'] = pd.DataFrame()
```

4. **读取问卷结果数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_agent_survey
    ORDER BY day, t
    """
    data['surveys'] = conn.execute(query).df()
    print(f"Survey results: {len(data['surveys'])} records")
except Exception as e:
    print(f"Failed to read surveys: {e}")
    data['surveys'] = pd.DataFrame()
```

5. **读取全局提示数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_global_prompt
    ORDER BY day, t
    """
    data['global_prompts'] = conn.execute(query).df()
    print(f"Global prompts: {len(data['global_prompts'])} records")
except Exception as e:
    print(f"Failed to read global prompts: {e}")
    data['global_prompts'] = pd.DataFrame()
```

6. **读取指标数据**

```python
try:
    query = f"""
    SELECT * FROM agentsociety.as_{table_suffix}_metric
    ORDER BY step
    """
    data['metrics'] = conn.execute(query).df()
    print(f"Metrics: {len(data['metrics'])} records")
except Exception as e:
    print(f"Failed to read metrics: {e}")
    data['metrics'] = pd.DataFrame()
```

获取实验数据并查看概览：

```python
experiment_data = get_experiment_data(exp_id)

print("\n=== Data Overview ===")
for table_name, df in experiment_data.items():
    if not df.empty:
        print(f"{table_name}: {len(df)} records, {len(df.columns)} columns")
        if 'day' in df.columns:
            print(f"  Time range: {df['day'].min()} - {df['day'].max()} days")
```

### 数据分析

现在，所有实验数据都被提取为方便分析的pandas DataFrame，可以根据你的实验需要开始数据分析了！
