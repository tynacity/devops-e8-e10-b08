# B08 E8–E10 MDFixer 实验

本仓库承接 [原 E5–E7 仓库](https://github.com/ISSUE808/devops-e5-e7-b08) 的完整提交历史，以原最终提交 `3fdc90f` 为起点，新增教师 E8–E10 实验和成员 4（241880492）的贡献。原 E7 workflow 保留，新 `e8e10-quality-gate` 同时验证 A/B 两轨三个阶段。

本次入口：[组内验收索引](docs/E8-E10/验收索引.md)、[成员 4 个人报告](docs/students/241880492/e8-e10/个人报告.md)、[决策记录](docs/students/241880492/e8-e10/ADR.md)、[AI 使用记录](docs/students/241880492/e8-e10/AI_USAGE.md)。成员 1（241880528）的 E8 贡献已通过 [PR #2](https://github.com/tynacity/devops-e8-e10-b08/pull/2) 合并；成员 2（241880529）的 E9 去重、隐式规则扩展及个人证据已通过 [PR #4](https://github.com/tynacity/devops-e8-e10-b08/pull/4) 验收合并。成员 3（241880546）的 E10 已通过 [PR #6](https://github.com/tynacity/devops-e8-e10-b08/pull/6) 验收合并。至此，四名成员的组内交接完成。

当前 GitHub 地址由成员 4 新建，用于本阶段 CI 和 PR；[GitLab E8-E10-B](https://git.nju.edu.cn/noth1ng/devops_labs08/-/tree/E8-E10-B) 保留先前公共基线。按 2026-11-06 组内确认，本次仓库地址不设限，验收使用上列 GitHub 仓库。旧 PR 和 Actions 记录留在原仓库，新仓库的提交历史不替代旧平台证据。

## E5–E7 历史交付说明

以下内容保留原交付文本，其中“当前”“本次”和原成员编号均指 E5–E7 阶段，不代表 E8–E10 已完成全组验收。

本仓库以 `DevOps_1020_Student_Cloud.zip` 的 B-draft 教学参考实现为基线，整合本组固定候选及成员 3 的新增测试。真实 GitHub CI、main 分支保护、失败 PR 拒绝及同一 PR 修复合并已完成；2026-10-25 已补齐 E5 独立成功构建与禁网运行、新版 doctor 真实自检记录。当前材料核对的 11 项均为 PASS；具体交付版本和对应 CI 见证据索引及离线包清单。尚未向教学平台提交，不等于已获助教最终验收。

报告入口：[实验报告](docs/实验报告.md)、[验收记录](docs/验收记录.csv)、[证据索引与离线备份说明](docs/证据索引.md)。

最终交付入口为 [`main`](https://github.com/ISSUE808/devops-e5-e7-b08/tree/main)。本次正常 PR 的合并 SHA、main 对应 CI、镜像及原始 artifact 见[主线交付验收记录](work/final-main-delivery-20261025/MAIN_DELIVERY_ACCEPTANCE.md)和包内 `DELIVERY_MANIFEST.json`；以该记录的实际结论为准，不用历史 PR #1 代替本次合并证明。

合并前的整理分支为 [`docs/e5-e7-report-and-acceptance`](https://github.com/ISSUE808/devops-e5-e7-b08/tree/docs/e5-e7-report-and-acceptance)。已验证代码基准 [`1a2bc46817276f0016cd28cbe8d3925b3acbded6`](https://github.com/ISSUE808/devops-e5-e7-b08/commit/1a2bc46817276f0016cd28cbe8d3925b3acbded6)及其 [CI 40115868439](https://github.com/ISSUE808/devops-e5-e7-b08/actions/runs/40115868439)、后续[文档补充提交记录](work/document-delivery-20261025/CI_DOCUMENT_DELIVERY_ACCEPTANCE.md)分别保留，不与最终 main 合并版本混用。各阶段均核对 15 项主机测试、26 项服务测试及五个真实场景；原始证据随离线包提供。

## 代码和候选来源

- 教师提供服务实现、原有 24 项测试、门禁脚本、镜像与依赖锁文件；本轮不修改生产算法。
- 成员 3（241880492）新增镜像检查失败测试，验证可解析 stdout 不能覆盖非零退出码，失败时不得运行程序。
- 成员 4（241880546）负责接收核对、整合新增测试和本组候选、调整 CI 候选输入及归档信息，完成分支保护与失败/恢复/合并验证、报告和证据整理；另按课程演示添加并恢复 1 项 version 返回码测试。当前共 26 项服务测试。
- 主机自检另作小样例适配：`scripts/doctor.py` 的最低可见内存改为 3.5 GiB，保留其余下限和建议值；新增 `scripts/tests/test_doctor.py` 的 15 项独立测试，并接入 CI 单独执行和归档。这 15 项不是服务测试，不将历史 26 项改写为 41 项；每次 CI 的结果与源码 SHA 分别记录。
- 最终候选：[group-E5-20261022.Dockerfile](fixtures/ci-candidates/group-E5-20261022.Dockerfile)；[来源记录](fixtures/ci-candidates/group-E5-20261022.provenance.json)保留原始字段，精确模型版本未单独记录。
- 原服务器位置为 `/root/devops-course/DevOps_1020_Student_Cloud/labs/B-draft/work/candidate/Dockerfile`，接收自成员 3 的 `E7-member3-241880492-20261023.tar.gz`，转存为上述仓库路径，未改变候选内容。

固定候选 SHA-256（保留 LF 换行，不要改写候选字节）：

```text
f4c86d4ee120d8a9114b1454d3eb23b5014eb326cc5b524cb291bc3f67e4eccd
```

来源记录中的 `BUILT_AND_VERIFIED` 和镜像 ID 指历史 E6 运行，不代表新提交已通过 CI。教师 DeepSeek 候选保留供显式 `--replay` 使用，但默认 CI 已改用本组候选。

## 云主机运行

在有可用 Docker 的本组 Linux 云服务器、此仓库根目录执行。使用自己的目录和镜像标签，每次重跑换新的 `--out`，不要覆盖队友证据：

```bash
python3 scripts/lab_cloud.py doctor
python3 scripts/lab_cloud.py build --image course1020-draft:241880546-e7 --out work/member4-build-01 --build-timeout 1200
python3 scripts/lab_cloud.py gate --image course1020-draft:241880546-e7 --candidate fixtures/ci-candidates/group-E5-20261022.Dockerfile --out work/member4-e7-01 --build-timeout 600
```

预期为 26 项服务测试及五个真实场景全部通过，整体门禁退出码 0。故障场景返回 1 可以符合预期；超时场景必须在候选构建成功后发生，并有容器清理证据。旧 Makefile/Compose 属于 E4 接口，本次以 `lab_cloud.py` 为入口。上述命令供新的运行使用，不是历史证据的原始命令；后者保存在各运行目录的 `command.json`。

## CI 与证据

根目录 `.github/workflows/e7-quality-gate.yml` 的检查名为 `e7-b-quality-gate`。CI 核对本组候选与 provenance 的哈希，保存候选副本及来源记录，再扫描源码/历史、构建和扫描服务镜像、运行完整门禁；无论通过或失败都归档 `work/ci/`，保留 14 天。

|阶段|真实记录|结果|
|---|---|---|
|正常 CI|[39992014649](https://github.com/ISSUE808/devops-e5-e7-b08/actions/runs/39992014649)|当时 25 项测试及五场景通过|
|PR #1 故意失败|[40077686673](https://github.com/ISSUE808/devops-e5-e7-b08/actions/runs/40077686673)|1 failed、25 passed，普通合并被实际拒绝|
|同一 PR 恢复|[40080265595](https://github.com/ISSUE808/devops-e5-e7-b08/actions/runs/40080265595)|26 项测试及五场景通过|
|合并后 main|[40080532893](https://github.com/ISSUE808/devops-e5-e7-b08/actions/runs/40080532893)|26 项测试及五场景通过|

[PR #1](https://github.com/ISSUE808/devops-e5-e7-b08/pull/1) 已正常合并为 `9fa0267fb51f9572a59dcb706d4f9bb0ffff0baf`。必需检查为 `e7-b-quality-gate`，要求分支保持最新并约束管理员；未使用绕过。演示修正的是故意写错的测试预期，不是生产算法缺陷。原始 artifact、拒绝合并日志和配置快照已下载，离线位置见证据索引。

## 已知限制与配套材料

- 本实验验证 hello E3 教学样例及保存的模型候选，不是完整在线模型迭代或论文项目全集复现。
- 已接收 E5/E6/E7 原始材料，并在本地忽略目录 `work/handoff/` 保留副本。2026-10-24 的 1200 秒、7200 秒 E5 失败补测均保留。北京时间 2026-10-25 00:06 的新补测保持候选和输入不变，仅在构建中启用本机临时 Debian 下载转发，约 42.9 秒构建成功，随后按所得镜像 ID 禁网运行，退出 0、输出 `hello E3`；独立核验见 `work/server-supplement-success-20261025/verification.json`。
- 四名成员姓名学号、云主机系统/资源/工具版本已补齐。课程统一分配主机为 Ubuntu 22.04.5、2 CPU、可见内存 3.5 GiB、Docker 29.1.3；新版 doctor 于北京时间 2026-10-25 00:59 退出 0、`problems: []`，环境项据此关闭。最新可用磁盘为 67.8 GiB；建议值警告和旧 4 GiB 阈值失败原样保留。真实记录在 `work/doctor-env-accepted-20261025/`；仅执行个人目录的新副本，没有覆盖共享仓库原脚本或修改 Git 身份。CI 环境与云主机分开记录。
- 学生包 `docs/03_B轨道操作指南.md`、`docs/04_GitHub_CI与合并门禁.md`、`ci/` 和 `templates/` 是配套指南、演示配置及报告模板；本地位于仓库外的 `course-support/`，其相对路径不等同于原学生包的 `../../ci/`。
- `work/` 默认忽略，但最终需另外备份并交付原始日志及下载的 CI artifact；禁止提交 `.env`、Token、SSH 私钥或登录文件。

## E11–E12 前期交接

新增入口、固定样例 CI 与 TinyExpr 真实项目输入见 [交接说明](docs/E11-E12/交接说明.md)。本阶段尚需完成组件适配、镜像环境交接、独立报告消费、API 与云主机验收。
