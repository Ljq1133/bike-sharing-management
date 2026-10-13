# 共享单车管理系统

数据库课程项目，使用 FastAPI、SQLAlchemy 和 PostgreSQL 实现用户注册登录、车辆管理、借还车、评分与维修记录。提供静态网页操作界面；SQLite 可用于快速本地演示。

## 功能与实现

- JWT 登录与单会话令牌管理，维护人员通过邀请码注册。
- 车辆位置查询、附近车辆筛选、借还车状态流转及使用记录。
- 用户、车辆、租借、维修记录的关系模型与 ORM 数据操作。
- HTML/CSS/JavaScript 界面、OpenAPI 文档及 Docker Compose 启动配置。

数据库模型见 [models.py](app/models.py)，业务操作见 [crud.py](app/crud.py)，实际运行入口为 [server.py](app/server.py)。`app/main.py` 是早期内存演示实现，数据库版本使用 `app.server:app`。

## 本地快速运行

使用 Python 3.11；依赖保留课程版本，Python 3.14 未作为支持环境。以下命令在仓库根目录执行。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = 'sqlite:///./dev.db'
$env:SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
$env:MAINTAINER_INVITE = 'local-demo-invite'
.\.venv\Scripts\python.exe scripts/create_db.py
.\.venv\Scripts\python.exe scripts/seed_bikes.py --count 20 --max-radius 2
.\.venv\Scripts\python.exe -m uvicorn app.server:app --host 127.0.0.1 --port 8000
```

- 界面：<http://127.0.0.1:8000/static/gui.html>
- 接口文档：<http://127.0.0.1:8000/docs>
- 车辆列表：<http://127.0.0.1:8000/api/bikes>

注册密码应超过 8 位且包含字母、数字。维护人员注册填写当前 `MAINTAINER_INVITE`。初始化脚本生成虚构车辆；重复运行会追加数据。

## PostgreSQL 与 Docker

复制 `.env.example` 为 `.env`，填写 `POSTGRES_PASSWORD`、`SECRET_KEY`、`MAINTAINER_INVITE`。Compose 使用同一组配置连接 PostgreSQL，并等待数据库就绪。

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写上述三项；密码建议使用字母和数字，避免连接 URL 转义问题。
docker compose up -d --build
docker compose exec web python scripts/seed_bikes.py --count 20 --max-radius 2
```

访问地址与本地演示相同。宿主机运行 PostgreSQL 的说明见 [README_WINDOWS.md](README_WINDOWS.md)。Python 直接启动时通过进程环境变量配置；`.env` 由 Compose 读取，Python 本身不会自动加载它。

## 目录

```text
app/          API、关系模型、认证及静态界面
scripts/      建表、虚构车辆初始化、诊断与本地准备
docs/         验证记录和项目来源
```

`scripts/clear_data.py` 会清空车辆、租借和维修记录，仅在可丢弃的本地演示数据库使用。

## 项目来源与验证

这是课程项目的展示版本。功能清单描述仓库整体实现，不代表团队中所有代码均由同一人编写；简历中的个人贡献应按实际分工填写。

见 [来源说明](docs/SOURCES.md) 与 [本次验证记录](docs/VALIDATION.md)。
