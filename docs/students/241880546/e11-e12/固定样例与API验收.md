# 成员3固定样例与API验收

学号：241880546；B08；日期：2026-11-10。源码提交：`12c3c99c0027c189a8ff4d5ff307052469e40b8b`。

本阶段不依赖A组的固定样例集成、共享API和SSH转发验收通过。检测使用现有教学适配器；正式A组报告与TinyExpr完整E12继续待联调。

## 本人工作

新增DRAFT下游运行器和宿主挂载映射，将全量/增量检测、补丁生成、验证和重检放入实际项目镜像。固定样例候选补齐Git/strace并保留原项目指令；API新增隔离目录、明确容器身份和原子状态持久化。新增6项个人测试覆盖真实HTTP幂等/冲突、下载哈希、越界、未完成产物、恢复及挂载映射。

## 输入与运行身份

|项目|实测值|
|---|---|
|固定样例base|`26ff07e843a341a00c36052beb336a8fc1a2f16f`|
|固定样例target|`0e2793578d7073bb1f65de585bb6767d28aed4f3`|
|新候选SHA-256|`9c4dfca1658e2775bbe8750d70a0d3b20892ae0d77ce2bd9cd4f518425db0721`|
|CLI job_id|`job-01ef50021cbe48cf86ad859ad7d6cd12`|
|CLI trace_id|`trace-db23f38b4a7d438d98c21f2343a8e8d5`|
|CLI DRAFT镜像|`sha256:cbfd2923359bc49604aa6661414c7df7771e1e8299d871a489b7b473f4ee295a`|
|API job_id|`job-8ac8f58436a94373b5ea9aed3d94198d`|
|API trace_id|`trace-73bc4064a6b641cbbfd54af38d34618b`|
|API DRAFT镜像|`sha256:7f331e8929b60b7d8bf9ca100ca1a98578cbb6f95391a77f72a715b792e3f3f5`|
|服务器API|`127.0.0.1:18546`，实例`e12-241880546-ae092326febb`|
|SSH客户端|本机`127.0.0.1:18080`转发到服务器API，复用原API任务|

CLI与API为两次独立构建。同次编排五阶段共享外层job_id/trace_id，full-check属于base，其余目标阶段属于target；各任务内7项下游操作均使用各自DRAFT输出的实际镜像与本轮工作副本。成员1原候选原样保留，新候选单独记录哈希。

## 验收与原件

以下链接相对于本目录；原始记录逐字节保存，未改写任务身份或运行路径。

|验收项|实际结果|证据|
|---|---|---|
|测试与回归|24项E11/E12测试及22项E8–E10回归通过|[测试](evidence/fixed-api-ae092326febb/contracts.log)、[回归](evidence/fixed-api-ae092326febb/e8e10-regression.log)|
|CLI五阶段|五阶段成功，最终无MD，7项下游实际复用镜像|[CLI结果](evidence/fixed-api-ae092326febb/cli/result.json)、[运行命令](evidence/fixed-api-ae092326febb/cli/execution-runtime.json)、[重检](evidence/fixed-api-ae092326febb/cli/recheck.json)|
|API与下载|五阶段成功；下载字节、清单和响应头SHA一致|[API清单](evidence/fixed-api-ae092326febb/http/manifest.json)、[补丁](evidence/fixed-api-ae092326febb/http/downloads/candidate.patch)、[API运行命令](evidence/fixed-api-ae092326febb/http/downloads/execution-runtime.json)|
|幂等与路径保护|同键同输入同任务；不同输入409；未完成产物409；越界/Git路径404|[总结果](evidence/fixed-api-ae092326febb/result.json)、[HTTP原始请求响应索引](evidence/fixed-api-ae092326febb/http/CASE_INDEX.json)|
|四类报告拒绝|错误schema、旧commit、错误kind、文件篡改按预期拒绝|[错误码](evidence/fixed-api-ae092326febb/consumer-rejections.json)|
|真实重启|已完成任务保留；实际RUNNING/QUEUED任务转为FAILED/SERVER_RESTARTED；幂等记录保留|[重启前](evidence/fixed-api-ae092326febb/before-restart-states.json)、[重启后](evidence/fixed-api-ae092326febb/after-restart-states.json)|
|SSH与源码保护|本机访问同一实例和job，下载通过；原输入与工具跟踪文件字节未变化|[SSH结果](evidence/fixed-api-ae092326febb/ssh-client/SSH_TUNNEL_VERIFIED.json)、[输入前](evidence/fixed-api-ae092326febb/input-before.json)、[输入后](evidence/fixed-api-ae092326febb/input-after.json)、[工具前](evidence/fixed-api-ae092326febb/tool-source-before.json)、[工具后](evidence/fixed-api-ae092326febb/tool-source-after.json)|

原始归档`241880546-e12-fixed-ae092326febb.tar.gz`的SHA-256为`0b99e88264aeb381f4f0fe39bb366fd34ea195a5a94713f09e205193b034ddaf`，内部清单542个文件通过校验。完整归档保存在工作目录的`e12_fixed_api_241880546/evidence/ae092326febb/`，按课程要求另行备份。

本目录摘录原始记录，逐文件哈希见[SHA256SUMS](evidence/fixed-api-ae092326febb/SHA256SUMS)，综合核对见[VERIFIED_ACCEPTANCE.json](evidence/fixed-api-ae092326febb/VERIFIED_ACCEPTANCE.json)。HTTP请求索引根据原始日志生成，所引用的请求元数据和响应原始字节均保留。

## 待继续

接收A组检测侧源码、准确版本及同一TinyExpr base/target的本轮报告、生产者清单和产物哈希，完成真实A→B消费与TinyExpr五阶段/API联调。当前结果不计作正式A组输入或TinyExpr完整E12。代码与验收资料尚未推送。
