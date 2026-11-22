# TestLedger｜测试执行与缺陷管理平台

TestLedger 记录测试计划、用例执行结果和失败产生的缺陷。计划摘要汇总失败执行数和未关闭缺陷数。项目使用 FastAPI、SQLAlchemy、PostgreSQL 17、Alembic 和 pytest，通过 Swagger UI 展示 HTTP 操作，并通过官方 Python MCP SDK 提供本地只读查询。

## 从克隆到运行

准备 Python 3.12、Git、Docker 和 Docker Compose V2，启动 Docker 引擎。下列命令均在仓库根目录执行。私有仓库需要已获访问权限的 GitHub 账号。

```sh
git clone https://github.com/kita80387694/test-ledger.git
cd test-ledger
python -m venv .venv
```

Windows PowerShell

```powershell
Copy-Item .env.example .env
. .\.venv\Scripts\Activate.ps1
```

macOS 或 Linux

```sh
cp .env.example .env
source .venv/bin/activate
```

安装本机演示和测试依赖，启动服务，再迁移和初始化演示数据。

```sh
python -m pip install -r requirements-dev.txt
docker compose up -d --build --wait
docker compose exec -T api python -m alembic upgrade head
docker compose exec -T api python -m testledger.seed
```

如果 PowerShell 限制激活脚本，可用 `.\.venv\Scripts\python.exe` 执行下文的主机端 Python 命令。Docker 容器内的 Python 命令保持原样。

打开 [Swagger UI](http://127.0.0.1:8000/docs) 或查看 [三分钟面试演示顺序](docs/swagger-demo.md)。Swagger 静态资源随镜像提供，浏览器从本机 API 加载。种子命令可重复执行，打印固定的样例计划 ID，并保留样例缺陷已有的状态。修改演示账号密码后可重新运行种子命令使配置生效。

## 主演示和测试

主演示命令在 Windows、macOS 和 Linux 上使用同一 Python 模块入口。每次运行创建两个带独立 ID 的计划，通过真实 HTTP 和 MCP stdio 连接校验缺陷 ID、角色权限及关闭后的统计。

```sh
python -m testledger.demo
```

验收时连续运行两次命令，再启动独立 PostgreSQL 测试容器并运行完整的 pytest。

```sh
python -m testledger.demo
python -m testledger.demo
docker compose --profile test up -d --wait test-db
python -m pytest -q
```

pytest 通过 `TEST_DATABASE_URL` 连接 `test_ledger_test` 并自动执行 Alembic 迁移。测试库使用单独的容器、端口和凭据。测试夹具让接口的提交使用保存点，并在每项测试后回滚外层事务。检查迁移与模型是否一致可运行 `docker compose exec -T api python -m alembic check`。

结束后运行 `docker compose --profile test down`。演示库保留在 Compose 卷中，测试库使用临时文件系统。

## 登录和权限

下表凭据仅供本地演示。服务和脚本从环境变量或根目录的 `.env` 读取配置。更改数据库密码时同步修改相应连接串，使用 URL 安全字符。JWT 签名密钥至少 32 个字符，令牌默认有效 60 分钟。

| 账号 | 本地示例密码 | 读取计划数据 | 创建计划、登记执行、登记缺陷 | 推进状态或关闭缺陷 | 重开已关闭缺陷 |
| --- | --- | --- | --- | --- | --- |
| `admin` | `admin-local-demo` | ✓ | ✓ | ✓ | ✓ |
| `tester` | `tester-local-demo` | ✓ | ✓ | ✓ | |
| `viewer` | `viewer-local-demo` | ✓ | | | |

`POST /auth/token` 接收表单字段 `grant_type=password`、`username` 和 `password`。随后使用 `Authorization: Bearer <access_token>`。密码以 Argon2 哈希保存。服务端检查 JWT 签名和时效，并从数据库读取该账号的当前角色。三个角色均可读取所有计划，查询结果按请求中的计划 ID 隔离。

## API

| 方法及路径 | 行为 |
| --- | --- |
| `POST /plans` | 创建测试计划 |
| `POST /plans/{plan_id}/executions` | 登记用例标识和 `passed` 或 `failed` |
| `POST /executions/{execution_id}/defects` | 为失败记录创建状态为 `open` 的缺陷 |
| `PATCH /defects/{defect_id}/status` | 更新缺陷状态 |
| `GET /plans/{plan_id}/summary` | 读取计划摘要和两项计数 |
| `GET /plans/{plan_id}/failed-executions` | 分页查询该计划的失败执行 |
| `GET /plans/{plan_id}/open-defects` | 分页查询该计划中状态为 `open`、`in_progress` 或 `resolved` 的缺陷 |

两个列表接受 `offset` 和 `limit`，默认分别为 `0` 和 `20`，每页最多 `100` 条，偏移量最大为 `2,147,483,647`。结果按 UUID 稳定排序，响应提供 `items`、`offset`、`limit` 和 `has_more`。

常规流转为 `open → in_progress → resolved → closed`。`resolved → in_progress` 可退回处理中。`closed → in_progress` 由管理员执行。状态变更在 PostgreSQL 行锁内读取及校验，避免并发请求基于旧状态更新。

统一错误结构为 `{"error":{"code":"…","message":"…","details":[]}}`。无效或缺少凭据返回 `401`，权限不足返回 `403`，资源不存在返回 `404`，非法状态流转或为通过记录登记缺陷返回 `409`，请求校验失败返回 `422`。校验错误在 `details` 中给出字段路径和原因。

## 数据关系与统计

| 表 | 主要字段和关系 |
| --- | --- |
| `users` | UUID 主键、唯一账号、密码哈希、角色 |
| `test_plans` | UUID 主键、名称、描述、创建者外键 |
| `executions` | UUID 主键、计划外键、用例标识、执行结果、创建者外键 |
| `defects` | UUID 主键、执行记录外键、标题、描述、状态、创建者外键 |

一个计划下可重复登记同一用例的多次执行。一条失败执行可关联多个缺陷。复合索引覆盖计划与结果、执行与状态两条查询路径。计划摘要从计划左连接失败执行，再左连接未关闭缺陷。连接条件保留空计划和已无未关闭缺陷的失败执行。`COUNT(DISTINCT executions.id)` 对失败执行去重，`COUNT(defects.id)` 逐条计算未关闭缺陷。

## MCP

`python -m testledger.mcp_server` 启动 stdio 服务，供 MCP 客户端作为子进程运行。唯一的工具 `list_open_defects` 接收计划 UUID `plan_id`，返回该计划的缺陷 ID、执行 ID、标题和状态。服务使用 `viewer` 登录并访问同一个分页 HTTP 接口，无需数据库账号、外部模型或 API Key。主演示会初始化真实 MCP 会话、发现工具并在每次状态变化后调用它。 [官方 Python SDK v1.26.0](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0)
