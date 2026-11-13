# TinyExpr A→B 交接验收

B08 成员3，学号 241880546。课程服务器运行 `8d2fa1f23ff7` 于北京时间 2026-11-12 17:08 完成。A侧重新生成检测报告，B侧独立消费并修复。TinyExpr五阶段命令行、共享API服务器自测和A/B分机验收均已通过。

|项目|实际值|
|---|---|
|A 检测代码| `8355af8e45623855c3397442598bd07e27f1ec1a` |
|B MDFixer 代码| `12c3c99c0027c189a8ff4d5ff307052469e40b8b` |
|TinyExpr base / target| `fed53f8bd0f76ea069fb6333d8e65b5326694837` / `db16775c83f90ead79255cc124d2a5f62f58a3b3` |
|DRAFT 候选 SHA-256| `3beee82b336e419c91ef3f256fc5636542f627438f072bf9c13d371831e7d89d` |
|本轮实际镜像| `sha256:2edc8cc5e780f1f9c2693b9d742c943884259282c7d0f99d0d4a8134cd130f20` |
|A job / trace| `job-1c7b529d087849978cdd00fb31288727` / `trace-fc1992b44f314edea8934bb0af08cad3` |
|B job / trace| `job-de37b2c69ee447f68c649168578b2605` / `trace-96c3077366dd4825bf18e842952ce857` |
|输入报告 SHA-256| `4164970e69273de8c41718bcc96dcbbc7e13f5a5a35f252b95ed4ed0724d7180` |
|B 生成补丁 SHA-256| `e017fde9c9499d0d29d0592de55cc43a06ba20adb2aa5255475e00774fde4862` |

A用DRAFT重现缺少 `make` 的构建失败，随后用候选镜像通过行为验证。基线的 strace 图用于构建历史缓存，目标增量检测复用了 `example.o`、`tinyexpr.o` 和 `example` 三个目标的数据。目标全量和增量均发现两个对象漏声明 `tinyexpr.h`，报告覆盖链接目标。见[DRAFT结果](evidence/tinyexpr-ab-8d2fa1f23ff7/a/draft.json)、[A生产者记录](evidence/tinyexpr-ab-8d2fa1f23ff7/a/producers.json)、[原始增量报告](evidence/tinyexpr-ab-8d2fa1f23ff7/a/incremental-check.json)和[目标全量发现](evidence/tinyexpr-ab-8d2fa1f23ff7/a/target-full/findings.json)。

B在同一镜像中消费A报告的原始字节，用A任务的 `result.json` 核对目标提交、产物URI、SHA-256及job和trace。B生成的补丁在目标副本的 `Makefile` 中补齐两条依赖。八项修复检查均通过。修改头文件后两个对象与链接产物均重建，增量与干净构建的产物及输出一致，动态重检无缺失依赖。原始TinyExpr的23个跟踪文件前后字节一致。见[B回执](evidence/tinyexpr-ab-8d2fa1f23ff7/B-receipt-75b86703.json)、[运行记录](evidence/tinyexpr-ab-8d2fa1f23ff7/consumer-runtime/accept/runtime.json)、[补丁](evidence/tinyexpr-ab-8d2fa1f23ff7/b/accept/candidate.patch)、[重建时间](evidence/tinyexpr-ab-8d2fa1f23ff7/b/accept/validation/object-times.json)、[动态重检](evidence/tinyexpr-ab-8d2fa1f23ff7/b/accept/validation/recheck.json)、[源码前](evidence/tinyexpr-ab-8d2fa1f23ff7/original-source-before.json)和[源码后](evidence/tinyexpr-ab-8d2fa1f23ff7/original-source-after.json)。

|拒绝用例|实际拒绝码与证据|
|---|---|
|报告字节被改动|[`ARTIFACT_HASH_MISMATCH`](evidence/tinyexpr-ab-8d2fa1f23ff7/b/tampered/result.json)|
|报告与修复提交不匹配|[`STALE_REPORT`](evidence/tinyexpr-ab-8d2fa1f23ff7/b/stale/result.json)|
|报告 schema 错误|[`SCHEMA_MISMATCH`](evidence/tinyexpr-ab-8d2fa1f23ff7/b/schema/result.json)|
|产物类型错误|[`ARTIFACT_TYPE_MISMATCH`](evidence/tinyexpr-ab-8d2fa1f23ff7/b/kind/result.json)|
|故意漏修 `tinyexpr.o`|[`REPAIR_REJECTED`](evidence/tinyexpr-ab-8d2fa1f23ff7/b/incomplete/result.json)，动态重检仍发现该缺失依赖，候选回滚|

完整归档 `evidence-75b86703.tar.gz` 保存在工作目录的 `e12_ab_tinyexpr_241880546/evidence/8d2fa1f23ff7/`，归档内的538个文件均已核对。交付目录保留可直接查看的原始证据。A任务清单引用的全部产物可在原始归档内按路径查找。见[归档哈希](evidence/tinyexpr-ab-8d2fa1f23ff7/ARCHIVE_SHA256)、[交付文件校验清单](evidence/tinyexpr-ab-8d2fa1f23ff7/SHA256SUMS)和[本机核验结果](evidence/tinyexpr-ab-8d2fa1f23ff7/VERIFIED_ACCEPTANCE-75b86703.json)。

## 五阶段命令行和共享 API

课程服务器上的命令行任务和 API 任务各执行一次完整五阶段。每个任务内五阶段共用一组 job 和 trace，七次下游操作均使用该任务验证过的 DRAFT 镜像。MDFixer 核对并消费本轮增量报告，最终动态重检无缺失依赖，原始输入前后哈希一致。

|方式|运行编号|任务与核验|
|---|---|---|
|命令行| `0970c13ac7dc` | `job-878c23f009b043f38585e43a79b64dab`。24项Linux契约测试通过，归档360个文件通过校验。[五阶段结果](evidence/tinyexpr-cli-0970c13ac7dc/cli/result.json)、[测试日志](evidence/tinyexpr-cli-0970c13ac7dc/contracts.log)、[核验](evidence/tinyexpr-cli-0970c13ac7dc/VERIFIED_CLI-54bad441.json) |
|服务器 API 自测| `f588070fdc04` | `job-eb2e8a6af00742969bdcbc5e8b1fa125`，trace 为 `trace-e2cea815bb714db4bdddb2e253b3b136`。归档79个文件通过校验。[API清单](evidence/tinyexpr-api-f588070fdc04/http/manifest.json)、[实例配置](evidence/tinyexpr-api-f588070fdc04/service.json)、[核验](evidence/tinyexpr-api-f588070fdc04/VERIFIED_API-628d1a06.json) |

服务器 API 监听 `127.0.0.1:18547`，实例名为 `e12-tinyexpr-241880546`。同键同输入的两次提交返回同一任务，改变目标提交返回 `409 IDEMPOTENCY_CONFLICT`。下载的报告及补丁字节、清单和 `X-Content-SHA256` 一致。见[首次提交](evidence/tinyexpr-api-f588070fdc04/http/003.json)、[重复提交](evidence/tinyexpr-api-f588070fdc04/http/004.json)、[冲突](evidence/tinyexpr-api-f588070fdc04/http/005.json)、[增量报告响应头](evidence/tinyexpr-api-f588070fdc04/http/017.json)和[补丁响应头](evidence/tinyexpr-api-f588070fdc04/http/020.json)。

完整归档保存在工作目录的 `e12_tinyexpr_cli_241880546/evidence/0970c13ac7dc/` 和 `e12_tinyexpr_api_241880546/evidence/f588070fdc04/`。两次运行使用的 B 基线提交、实际改动文件哈希及 A 检测器版本见[命令行源码记录](evidence/tinyexpr-cli-0970c13ac7dc/source-versions.json)和[API源码记录](evidence/tinyexpr-api-f588070fdc04/source-versions.json)。

## 分机验收

B 端在本地电脑通过 SSH 转发访问实例 `e12-tinyexpr-241880546`。共享请求幂等键为 `tinyexpr-ab-f588070fdc04`，任务 `job-dd9b7f76b2cd4825bcee357edf83d745` 已成功，追踪编号为 `trace-b048fbed944f48b3a977e8fcd9657781`。重复提交复用同一任务，改变目标提交返回 `409 IDEMPOTENCY_CONFLICT`。五阶段报告及补丁共六个产物的实际字节、响应头和清单哈希一致，动态重检无缺失依赖。完整原始记录保存在工作目录的 `e12_tinyexpr_api_241880546/ab-client/evidence-B-bfaf459f/`。见[B端核验](evidence/tinyexpr-peer-B-bfaf459f/peer-verification.json)、[任务清单](evidence/tinyexpr-peer-B-bfaf459f/manifest.json)和[交付文件校验清单](evidence/tinyexpr-peer-B-bfaf459f/SHA256SUMS)。

A 端于北京时间 2026-11-12 20:52 从另一台电脑建立 SSH 转发并运行客户端，复用了 B 端 20:16 提交的任务。A 回传的 51 个文件通过校验，A 端 12 组、B 端 17 组 HTTP 记录均通过复核。两端请求、实例、任务编号、追踪编号、执行镜像和五阶段清单一致，六份产物逐字节相同。隧道在六份必需产物下载完成后关闭，额外运行日志的下载随后中断。见[A端核验](evidence/tinyexpr-peer-A-047ccf5a/peer-verification.json)、[隧道健康检查](evidence/tinyexpr-peer-A-047ccf5a/tunnel/tunnel-health.json)和[双端核对结果](evidence/tinyexpr-peer-A-047ccf5a/A-B-comparison.json)。含主机名和 SSH 登录细节的原始记录随 A 组回传及 B 端本地证据保存。
