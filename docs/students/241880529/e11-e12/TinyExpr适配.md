# B 组 2 号 TinyExpr MDFixer 交接

| 项目 | 本次验证输入 |
| --- | --- |
| 学号 | `241880529` |
| 工具仓库 | [tynacity/devops-e8-e10-b08](https://github.com/tynacity/devops-e8-e10-b08) |
| 工具分支 | `student/241880529/e11-e12` |
| 适配源码提交 | `9b672378477f86d7e65dcf4a90bfc49e4ecf7e69` |
| 适配前工具基线 | `6cc7608c45473a2a9a67914fbfb70d40197e04af` |
| TinyExpr base | `fed53f8bd0f76ea069fb6333d8e65b5326694837` |
| TinyExpr target | `db16775c83f90ead79255cc124d2a5f62f58a3b3` |
| 本次环境 | WSL Ubuntu 22.04，Python 3.10.12，GCC 11.4.0，GNU Make 4.3，strace 5.16 |

## 已验证

- 固定 target 的 BuildChecker 动态基线发现 `example.o → tinyexpr.h` 和 `tinyexpr.o → tinyexpr.h`。本地修复输入来自这份实际检测，保留系统调用位置和声明侧已有依赖。
- MDFixer 输出的补丁只添加两条对象规则，原 `.c.o` 编译 recipe、链接 recipe 和标志均保留。重复的同一条 finding 只生成一处编辑。
- `git apply --check`、`make example` 和 `python3 course/verify_example.py` 通过，实际输出的数值为 `15.198684`。未改动头文件时不会重建。加一条头文件注释后，两对象均重编译且可执行文件重新链接。增量和干净构建的两个对象、可执行文件 SHA-256 及程序输出一致。对恢复原头文件后的修复版本重跑 `strace`，选定构建图中无 MD。
- 反向输入故意省去 `tinyexpr.o` 的 MD。候选能构建、输出也正确，但漏重编译 `tinyexpr.o`，动态重检仍有 MD，进程退出 1，结果为 `REPAIR_REJECTED` 和 `rollback=true`。验证在沙箱中执行，拒绝时目标副本的 Makefile 字节保持原样。
- E11/E12 共 18 项测试通过，含新增 5 项，覆盖去重、对象范围、越界符号链接、内层旧 commit 以及报告和生产者的身份、哈希绑定。E8–E10 的 22 项回归测试通过。

入口为 [`tinyexpr_repair.py`](../../../../labs/e11e12/tinyexpr_repair.py)，调用 [`lab.py`](../../../../labs/e8e10/lab.py) 生成补丁，新增测试位于 [`test_tinyexpr_repair.py`](../../../../labs/e11e12/test_tinyexpr_repair.py)。以上三份工作树源码与首次 TinyExpr 适配证据包逐字节相同。`provenance.json` 记录工作树和 Git blob 的哈希及换行差异。

## 在 DRAFT 镜像内复跑

在工具仓库根目录使用 Linux。首次运行时克隆 [TinyExpr fork](https://github.com/tynacity/tinyexpr/tree/course/e11-e12)；已有 `data/real-project` 且含目标提交时可直接使用。将 `image` 设为本机可用的 DRAFT 镜像完整 ID。两份固定输入已随源码提交，逐字节对应此前正反运行各自的 `consumed-report.json`。

```bash
git clone --branch course/e11-e12 https://github.com/tynacity/tinyexpr.git data/real-project
target=db16775c83f90ead79255cc124d2a5f62f58a3b3
image=sha256:3bf2f242c20847f692988862afa932f6da67b5fd36cfa8b263145d6a11b72227
docker image inspect "$image" >/dev/null
stamp=$(date +%s)

python3 labs/e11e12/tinyexpr_repair.py \
  --repo data/real-project --target "$target" \
  --report fixtures/e11e12/tinyexpr-md/accept.json \
  --report-sha256 3697f5df5b7075b95273d11f937e378f2e5917d8c189cd9044164ea0db5ebe99 \
  --image-id "$image" --out "work/tinyexpr-accept-$stamp"

reject_rc=0
python3 labs/e11e12/tinyexpr_repair.py \
  --repo data/real-project --target "$target" \
  --report fixtures/e11e12/tinyexpr-md/reject-incomplete.json \
  --report-sha256 74f162948eadc90bd5c60ce536057834474a8e3763c498deba4b086032656e9d \
  --image-id "$image" --out "work/tinyexpr-reject-$stamp" || reject_rc=$?
test "$reject_rc" -eq 1
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["error"]["code"] == "REPAIR_REJECTED"' \
  "work/tinyexpr-reject-$stamp/result.json"
```

## 补交证据索引

以下路径均相对于[补交证据 ZIP](evidence/tinyexpr-member2-supplement.zip)解压目录。`SHA256SUMS.txt` 核对归档内容。上一轮的候选和完整正反结果沿用原交付。

| 内容 | 解压后路径 |
| --- | --- |
| 源码 SHA、环境、测试命令、退出码和输入关联 | `provenance.json` |
| 18 项契约与适配、22 项 E8–E10 回归完整输出 | `tests/e11e12-tests.log`、`tests/e8e10-tests.log`，`tests/original/` 保留上次日志 |
| 固定 MD 的原始动态检测 | `baseline/tinyexpr-baseline-probe-20261110/` 内 `findings.json`、`trace/t.*`、`actual-graph.json`、`declared-graph.json` 和 `make-db.txt` |
| 正反用例的跟踪文件 SHA 对照 | `source-audit/accept/source-hashes.tsv`、`source-audit/reject/source-hashes.tsv` |
| 正反用例的源仓库前后状态和目标副本状态 | `source-audit/{accept,reject}/source-before.json`、`source-after.json`、`target-after.json`，包含 Git 状态、`git diff --summary`、`--numstat`、换行信息及每文件哈希 |
| 额外审计复跑的命令、退出码和结论 | `source-audit/{accept,reject}/command.json`、`stdout.log`、`stderr.log`、`run/validation/validation.json` |

原输入仓库的 23 个跟踪文件在正反两次运行前后的原始字节哈希分别相同。其中 21 个文件为 Windows 工作树的 CRLF，转成 LF 后与 Git 对象逐一匹配。容器的 `git diff --summary` 为空。目标副本从 Git 提交检出，表中 `target_checkout_sha256` 来自该提交对象；正向通过后只有目标副本的 Makefile 变化，反向拒绝后 23 个文件均匹配。验证沙箱是独立的可修改副本。

## 真实 E12 输入接入

收到 A 组同一 target 的 `incremental-check.json` 与生产者 `result.json` 后，用运行主机上的完整 DRAFT image ID 执行以下命令。镜像需要 Python 3.10+、Git、Make、GCC 和 strace。`report_sha` 取联调下载响应的 `X-Content-SHA256`，用于核对清单和实际文件。仓库、报告和输出路径都位于工具仓库下。

```bash
python3 labs/e11e12/tinyexpr_repair.py \
  --repo data/real-project --target db16775c83f90ead79255cc124d2a5f62f58a3b3 \
  --report work/a-tinyexpr/incremental-check.json \
  --producer-manifest work/a-tinyexpr/result.json --report-sha256 "$report_sha" \
  --image-id "$draft_image_id" --out "work/tinyexpr-e12-$(date +%s)"
```

独立 MDFixer 入口核对上下游 schema、kind、状态、commit、阶段 URI、`job_id`、`trace_id` 和 SHA-256。镜像模式把当前输入源码挂载进容器，在指定镜像内执行修复、构建和动态重检，并保存 `docker-execution.json`。真实 A 报告与共享 API 编排仍待联调。

## DRAFT 镜像复跑记录

- 本机 Docker Desktop `linux/amd64` 使用 1 号交接的原始 Dockerfile，SHA-256 为 `3beee82b336e419c91ef3f256fc5636542f627438f072bf9c13d371831e7d89d`。Docker Hub 认证端点超时，独立 BuildKit 实例通过 DaoCloud 读取相同的基础镜像摘要。初版复现 `make: not found`，候选构建并禁网运行成功，输出 `15.198684`。
- 本机镜像 ID 为 `sha256:3bf2f242c20847f692988862afa932f6da67b5fd36cfa8b263145d6a11b72227`。两次 MDFixer 验证都使用该 ID 和本地 BuildChecker 报告。正向复跑通过头文件增量重建、干净构建对照和全图动态重检，剩余 MD 为 0。反向用例保留 `tinyexpr.o → tinyexpr.h` 一条 MD，触发 `REPAIR_REJECTED`，目标副本 Makefile 与提交中的原始字节一致。
- 上一轮证据 ZIP 内的目录为 `work/tinyexpr-draft-amd64-20261110-03/`、`work/tinyexpr-mdfixer-container-20261110/` 和 `work/tinyexpr-mdfixer-rollback-container-20261110/`。两次 `docker-execution.json` 记录实际容器命令及退出码。
