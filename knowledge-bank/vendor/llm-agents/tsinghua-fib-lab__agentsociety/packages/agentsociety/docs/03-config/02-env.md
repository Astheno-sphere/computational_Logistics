# 环境配置

环境配置包含数据库、文件存储等基础设施设置。

## 配置字段

- `db` (DatabaseConfig): 数据库配置
  - `enabled` (bool): 是否启用数据库存储，默认true
  - `db_type` (str): 数据库类型，支持`sqlite`和`postgresql`
  - `pg_dsn` (Optional[str]): PostgreSQL连接字符串，使用PostgreSQL时必需
- `home_dir` (str): AgentSociety数据存储目录，默认`./agentsociety_data`

## 配置示例

**SQLite配置（适合开发和小规模实验）**：
```yaml
env:
  db:
    enabled: true
    db_type: sqlite
  home_dir: ./agentsociety_data
```

**PostgreSQL配置（适合生产环境）**：
```yaml
env:
  db:
    enabled: true
    db_type: postgresql
    pg_dsn: postgresql://user:password@localhost:5432/database
  home_dir: /var/lib/agentsociety
```