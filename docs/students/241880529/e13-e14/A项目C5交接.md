# A-HeaderFlow 正式配对项目 C5 交接

2026-11-18，成员 2，241880529。交成员 4 验收，供成员 3 接续集成。

## 本轮结论

在课程服务器 AMD64 环境、B-to-A C1 回执登记的实际 DRAFT 镜像内，消费 A 原始增量报告及生产者清单，执行正确补丁、漏依赖错误补丁、编译错误补丁三项验证。正确补丁被接受，两个错误补丁均返回 `accepted=false`、`rollback=true`。原 A 项目仓库 10 个跟踪文件的字节、HEAD、Git 状态和差异摘要前后完全一致。[完整证据包](evidence/member2-A-HeaderFlow-C5-20261118.zip) · [核验摘要](evidence/headerflow-c5-verification.json)

| 身份 | 完整值 |
| --- | --- |
| 工具实测提交 | `5aad22a5cc5a2516ecbcf505aaf73b1c1d68aafd` |
| 本人分支与 PR | `student/241880529/e13-e14` · [PR #14](https://github.com/tynacity/devops-e8-e10-b08/pull/14) |
| 项目 base | `88af5173a249ee4f30f3d7da51b20169db47d234` |
| 项目 target | `961f40cb8fbb71de304b782ff754522d59d51305` |
| A 来源 job | `job-6e7f20bbfc9c49adb76d8432ce08f542` |
| A 来源 trace | `trace-027e97ba3b724c3bb84a2026e4dc6ac8` |
| A 报告 SHA-256 | `c86c2db4b14c84df6f736044e6fcc3993f0a0a04cff7076355996d45ec0d323c` |
| 实际 DRAFT 镜像 | `sha256:596aa607c88a4c98d17ae5e808b08540a9d23d820a24c62c9969576655b18163` |
| 服务器目录 | `/root/241880529/headerflow-c5-20261118/repo` |

A 项目来源为成员 1 的 A 项目推进包中的独立 Git 仓库，报告及生产清单取自 `B-to-A-E13-20261117-v2-C1.zip`。本次恢复 Git 空 refs 目录后核对项目仓库根目录、base 祖先关系和 target。运行前还比较实际镜像 `/work` 内六个构建输入文件的 SHA-256，均与原项目匹配。该镜像复用已有 C1 的构建结果，本次执行的是独立 C5 验证。

## 注入及结果

原 C5 脚本按 H2 的 Makefile 字符串注入。A 项目原声明不同，本轮改为先由原始 A 报告生成完整正确补丁，再在独立注入副本中制造单一错误。补丁生成、依赖安全检查及修复验证沿用既有实现。

| 用例 | 注入与观察 |
| --- | --- |
| 正向 | 补齐三个 MISSING，补丁 SHA-256 为 `4d9e61596043231b12564b623b74a1b974519202ee491492fccb9c1654b89ee6`，与已有 C1 结果一致。构建、输出 `1`、头变化后输出 `2`、动态复检均通过，A 自带 `tests/verify_behavior.py` 输出 `A_HEADERFLOW_BEHAVIOR=PASS`。原 `main.o → unused.h` 冗余声明保留 |
| 漏 config.h | 从完整修复结果只去掉 main.o 的 config.h，其他修复保留。构建可成功，但头变化验证和 MD 重检失败，拒绝且回滚 |
| 编译错误 | 保留全部依赖修复，仅给 main.c 编译 recipe 加入非法 GCC 参数。构建失败，原始错误保存在 validation，拒绝且回滚 |

拒绝用例分别保存目标副本完整 HEAD、Git 状态及全部文件哈希；前后匹配。原始仓库的保护记录为归档 `run/source-before.json`、`source-after.json`。验证沙箱可修改，目标副本与原件分列取证。

## 测试及版本

按测试驱动开发新增 6 项注入回归，覆盖 A 的其他修复保留、编译注入隔离、H2 依赖顺序、缺探针依赖、缺编译 recipe 与错误注入类型。服务器实际镜像内通过 15 项成员 2 测试及 24 项既有契约测试。本机另以同一脚本对 H2 原输入复测，正向和两个拒绝路径通过。日志及实际 Docker 命令在证据包根目录。

本轮属于 C5 注入能力扩展，没有新增 MDFixer 修复算法缺陷。运行器为 [run_member2_c5.py](../../../../labs/e13e14/run_member2_c5.py)，测试为 [test_member2_c5.py](../../../../labs/e13e14/tests/test_member2_c5.py)。实测源码摘要见核验摘要，可与 `5aad22a…` 的 Git blob 核对。

## 复跑

将证据包 `inputs.zip` 解压至工具仓库 `data/headerflow`。文件转存包没有保存 Git 空目录项，按下面命令恢复 refs 目录并确认仓库根位置。代码在工具仓库根目录执行。

```bash
mkdir -p data/headerflow/project/repo/.git/refs/heads data/headerflow/project/repo/.git/refs/tags
git -C data/headerflow/project/repo rev-parse --show-toplevel
git -C data/headerflow/project/repo rev-parse HEAD
```

使用可取得的同一项目运行镜像，核对实际 ID 后执行。下列 ID 由服务器 Docker inspect 核验为 AMD64，本地或其他主机需自行取得匹配环境并登记实测 ID。

```bash
draft_image_id=sha256:596aa607c88a4c98d17ae5e808b08540a9d23d820a24c62c9969576655b18163
docker run --rm --network none --cap-add SYS_PTRACE --user 0:0 \
  -e HOME=/tmp -v "$PWD:/course" -w /course --entrypoint python3 "$draft_image_id" \
  labs/e13e14/run_member2_c5.py --repo /course/data/headerflow/project/repo \
  --target 961f40cb8fbb71de304b782ff754522d59d51305 \
  --report /course/data/headerflow/a-report/incremental-check.json \
  --producer-manifest /course/data/headerflow/a-report/result.json \
  --report-sha256 c86c2db4b14c84df6f736044e6fcc3993f0a0a04cff7076355996d45ec0d323c \
  --out /course/work/headerflow-c5-new
```

完整原始证据 ZIP 含 381 个条目，SHA-256 为 `e18b8611e9b1b9a4873d4db80dbe993d030605cc453758292b04002ff9c309c3`。解压后用 `sha256sum -c SHA256SUMS.txt` 校验。`host-run.py` 保存服务器真实启动命令，`commands.json` 保存容器镜像、挂载、退出码，`inputs.zip` 保存原项目、原报告与生产清单。

本次 C5 是独立组件调用，来源 job/trace 保持 A 原值，没有分配或补造 HTTP 任务身份。成员 4 可接收复验此项，成员 3 继续正式 HTTP 接入及 E14 四服务真实项目验收。双向交换签收、C7/C8 和最终门禁各自记录。
