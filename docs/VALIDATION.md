# 验证记录

## 已完成

- Python 3.11.17 隔离环境安装原 `requirements.txt` 全部依赖。
- 使用临时 SQLite 数据库与 FastAPI TestClient 验证：首页、静态界面、API 文档、注册、登录、身份查询、创建车辆、借车、还车、历史记录、退出接口；断言通过。
- PostgreSQL Compose 配置通过 `docker compose config --quiet`。
- Dockerfile 已移除重复的第二套镜像阶段和未提供的 Alembic/wait-for-db 文件引用。
- 源码 Python 语法、README 本地链接与 Git 提交文件清单检查通过。

## 验证边界

没有启动 PostgreSQL 容器或构建 Docker 镜像；SQLite 验证不能替代 PostgreSQL 分支验证。系统 Python 3.14 与课程依赖不兼容，运行说明使用 Python 3.11。

API 冒烟检查覆盖列出的流程，不是权限、安全或性能的完整审计。未声明已上线、生产可用或具备性能指标。
