# 三分钟 Swagger 面试演示

## 开始计时前

完成 [README](../README.md) 的启动、迁移和种子数据步骤。打开 [Swagger UI](http://127.0.0.1:8000/docs)，点击 **Authorize**，填写 `tester` 和配置中的 `DEMO_TESTER_PASSWORD`。示例密码为 `tester-local-demo`，仅供本地演示。保留 **client_id** 和 **client_secret** 为空。

展开 `POST /plans`，点击 **Try it out**，执行 `{"name":"Swagger interview"}`。复制响应中的计划 `id`。每轮演示新建计划，便于直接比较计数。

## 0:00–0:45 登记失败

展开 `POST /plans/{plan_id}/executions`，填入计划 ID，执行以下请求。复制响应中的执行记录 `id`。

```json
{"case_key":"CHECKOUT-001","result":"failed","notes":"Checkout total is missing"}
```

指出执行记录保存计划外键、用例标识和结果。同一用例可以登记多次执行。

## 0:45–1:30 创建缺陷

展开 `POST /executions/{execution_id}/defects`，填入执行记录 ID，执行以下请求并复制缺陷 `id`。

```json
{"title":"Checkout total is missing"}
```

调用 `GET /plans/{plan_id}/summary`，确认 `failed_execution_count=1`、`open_defect_count=1`。解释一条失败执行可以关联多个缺陷，摘要对执行 ID 去重。

## 1:30–3:00 关闭缺陷并复查

展开 `PATCH /defects/{defect_id}/status`，填入缺陷 ID，按顺序执行三次请求。

```json
{"status":"in_progress"}
```

```json
{"status":"resolved"}
```

```json
{"status":"closed"}
```

再次执行 `GET /plans/{plan_id}/summary`，确认 `failed_execution_count=1`、`open_defect_count=0`。如有时间，执行 `GET /plans/{plan_id}/open-defects`，展示空的 `items`。解释关闭操作更新缺陷状态，失败执行仍用于回溯。
