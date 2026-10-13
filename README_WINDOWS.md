# Windows 本地运行与 PostgreSQL 配置

最快演示方式是根目录 [README](README.md) 中的 SQLite 流程，无需管理员权限。以下是 PostgreSQL 分支；使用 Python 3.11，在仓库根目录执行。

## 创建数据库

先启动 PostgreSQL，使用 pgAdmin 或 `psql` 为本地演示创建用户和数据库。示例密码只用于说明，请自行替换。

```sql
CREATE USER bikeapp WITH PASSWORD 'replace_with_local_password';
CREATE DATABASE bike_db OWNER bikeapp;
```

## 安装与运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = 'postgresql://bikeapp:replace_with_local_password@127.0.0.1:5432/bike_db'
$env:SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
$env:MAINTAINER_INVITE = 'local-demo-invite'
.\.venv\Scripts\python.exe scripts/create_db.py
.\.venv\Scripts\python.exe scripts/seed_bikes.py --count 20 --max-radius 2
.\.venv\Scripts\python.exe -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

访问 <http://127.0.0.1:8000/static/gui.html>。环境变量只对当前终端及其子进程生效。

可用 `scripts/setup_windows.ps1` 创建虚拟环境并安装依赖；它不修改系统环境变量或自动创建 PostgreSQL 用户。连接诊断脚本是 `scripts/diag_conn.py`。密码带特殊字符时，需要进行连接 URL 编码。
