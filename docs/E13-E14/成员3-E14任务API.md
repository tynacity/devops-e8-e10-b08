# E14 四服务任务 API

E14 任务入口负责排队、调用四服务编排器和提供产物下载。HeaderFlow 使用 `mode=e12, profile=explicit`，TinyExpr 使用 `mode=e12, profile=tinyexpr`。E13 G2 的 `mode=e13-b` 请求继续提交给原服务。

## 启动

核对四个 Compose 角色在 `127.0.0.1:18181–18184` 的健康检查，并确认 Compose 的 `/course` 与任务 API 使用同一份仓库。配对项目和候选 Dockerfile 放在仓库的 `data/` 下。TinyExpr 还需要在 `data/tinyexpr-a-detector` 恢复约定的检测器版本。

在上述仓库根目录启动 E14 任务 API。每个部署使用自己的 `work/` 子目录，一个目录由一个 API 进程管理。

```bash
python3 -u labs/e13e14/jobs_api.py --port 18594 --root work/e14-api-acceptance
```

服务监听 `127.0.0.1`。`GET /health` 返回 `schema_version=e14-compose-1` 与 `service_id=course-e14-four-role`。

## 提交、轮询与下载

1. 把已核对的编排器请求放入正文的 `input` 字段，再加上 `idempotency_key`。输入的 `repo` 和 `candidate` 使用 `/course/data/…` 路径，`base` 和 `target` 使用完整的 40 位 SHA，配对项目需要填写准确的 `expected_output`。可在 `build_timeout` 指定本轮构建预算，单位为秒。
2. 向 `POST /v1/jobs` 发送 JSON，记录 HTTP 202 返回的 `job_id`。相同键和正文复用同一个任务，相同键和不同正文返回 409。
3. 请求 `GET /v1/jobs/<job_id>` 直到任务进入终态，保存状态和 `trace_id`。成功任务可对照 `draft → full-check → incremental-check → repair → recheck` 五阶段；失败任务保留已完成阶段和可下载的诊断产物。
4. 请求 `GET /v1/jobs/<job_id>/artifacts` 保存清单。将每条 `artifact://<job_id>/<path>` 转成 `GET /v1/jobs/<job_id>/files/<path>`，保留路径的分隔符并对各路径段做 URL 编码。比较下载文件的字节数、SHA-256 与清单，核对响应的 `X-Content-SHA256`。
5. 成功样例留存请求、任务状态、清单和下载产物。验收时核对阶段记录及角色请求中的 job/trace、DRAFT 镜像 ID、修复与动态重检结果、原项目保护记录。

进行中的任务请求清单或产物会收到 409。下载范围由任务清单限定，清单外路径返回 404，产物字节变化返回 409。重启会把未完成的任务标记为 `FAILED / SERVER_RESTARTED`，需要重试时使用新的幂等键。

## 本地复核

```bash
python3 -B -m unittest discover -s labs/e13e14/tests -p 'test_member3_e14*' -v
```

本地测试使用回环 HTTP 和模拟 Docker。课程服务器验收仍需记录实际 AMD64 镜像、样例运行、超时清理和恢复，并复核 API 下载的原始产物。
