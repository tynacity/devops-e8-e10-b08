# AI 使用记录：241880546

记录人：滕明杰；校区：苏州校区；小组：B08；本轮主责：E10。

辅助过程涉及 2026-11-03—06；整理日期：2026-11-06。

## 工具、模型与输入

- 工具：Codex。
- 输入：课程 E8—E10 手册与模板、组内分工、共享基线源码、终端回传、本人新增测试及下载的原始证据包。
- 服务器密码、GitHub 设备码、Token 和私钥未提供给助手。服务器登录和 GitHub 浏览器授权由本人完成。

## 辅助范围与采纳情况

1. 辅助理解成员 3 的 E10 任务，区分公共准备、基础矩阵、个人新增测试和最终交付。
2. 辅助编写个人环境与离线同步脚本。服务器缺少 gh 时使用个人目录中的官方二进制；Git HTTPS 克隆中断时使用带提交历史的 Git bundle，未关闭 TLS 校验。
3. 辅助编写 E10 执行编排，调用已有课程函数，保存输入、三次判定、字节副本和真实动态重检。其结果由实际服务器运行产生，不以模型预期替代执行。
4. 辅助编写 `Student241880546E10Tests`。采用“候选可应用但非法编译参数导致失败”的独立输入，以及 Patch 应用、错误原因、拒绝标志和源文件字节对照断言。
5. 辅助核对下载归档的 SHA-256、JSON、测试日志、7 个输入文件的字节对照及服务器/本地测试文件一致性，并整理交付文档。
6. 对照个人报告模板补充 E8/E9 基础流程编排，分别新建 OUT，核对旧报告拒绝、三种声明风格及原 E10 证据保持；根据下载的真实结果恢复三阶段五列总表。
7. 辅助编写 PR 创建与 CI 证据下载脚本，核对本人回传结果、两项 pull_request 运行元数据、artifact 和 CI 测试日志；分别记录 PR head、artifact 检出版本和本地备份校验值。

采纳的建议包括：保留旧证据、用新目录运行个人用例、保留失败 sandbox、使用本人的局部认证，以及在未提交阶段以“基线 SHA + 补丁/文件哈希”记录源码身份。没有记录额外被否决的模型修复候选；未把关闭 TLS、强制重置或借用他人认证作为处理方式。

## 人工参与与修改

本人确认职责和身份信息，在自己的终端执行启动命令、输入 SSH 密码、完成 GitHub 授权并回传实际结果。编排脚本自动执行内部步骤，因此不将这些内部命令描述为本人手工逐条输入。

PR #6 由本人在电脑 PowerShell 运行 `COMPLETE_PR.ps1` 后创建。该脚本使用本人已登录的 GitHub CLI，等待两项检查并下载 artifact；未执行合并。

新增测试和运行脚本由 AI 辅助编写；本轮没有单独记录本人对测试代码的额外手工改写。

## 实际验证

| 输入与运行 | 实际结果 | 证据 |
| --- | --- | --- |
| E8 基础流程，`work/e8-B-manual.IaiXfW` | 8 步退出 0；报告版本一致；候选只增补 config.h；旧报告拒绝；7 个源文件保持 | [E8 checks](evidence/e8/checks.json)、[旧报告拒绝](evidence/e8/expected-failure.json)、[字节对照](evidence/e8/source-comparison.json) |
| E9 三种风格，`work/e9-B-manual.Lc0bWf` | 6 步退出 0；三种补丁应用检查通过，原输入不变；macro 额外副本应用成功 | [E9 checks](evidence/e9/checks.json)、[字节对照](evidence/e9/source-comparison.json)、[应用副本](evidence/e9/apply-demo/Makefile) |
| E8/E9 补跑保护 | 原 E10 两份 OUT 及路径记录共 315 个受保护文件哈希前后一致；下载后交叉核对原 E10 包 121 个文件也一致 | [保护结果](evidence/supplement/protection-check.json)、[汇总](evidence/supplement/summary.json) |
| E10 基础矩阵，`work/e10-B-manual.1jq7NB` | 两次预期拒绝、一次正常接受；五项正常检查通过；动态重检 SUCCEEDED，无 MISSING | [基础 gate](evidence/baseline/gate.json)、[动态报告](evidence/baseline/dynamic-findings.json) |
| 个人新增编译失败候选，`work/e10-B-member3.JsgLLh` | Patch 可应用，构建报错，候选拒绝；7 个源文件字节保持 | [实际验证](evidence/personal/validation.json)、[字节对照](evidence/personal/source-comparison.json) |
| 定向与完整测试 | 1 项及 22 项均为 OK，退出码 0 | [定向日志](evidence/personal/targeted-tests.log)、[完整日志](evidence/personal/full-suite.log) |
| 归档下载与核对 | E10 及 E8/E9 原始包 SHA-256 一致，服务器测试文件与本地一致 | [E10 归档](evidence/server-evidence.tar.gz)、[E8/E9 归档](evidence/e8-e9-server-evidence.tar.gz)、[校验值](evidence/SHA256SUMS)、[源码身份](evidence/personal/source-state.txt) |
| PR #6 的两项 CI，head=`677c2191563cb636f3f9ac4c44e45c774eafaa7c` | E7、E8–E10 检查均 success；CI 完整 22 项测试含本人新增用例；B E10 三场景通过且动态重检无 MISSING | [E7 运行](evidence/ci/e7-run.json)、[E8–E10 运行](evidence/ci/e8e10-run.json)、[CI 日志](evidence/ci/unit-tests.log)、[B gate](evidence/ci/B-e10-gate.json) |
| PR artifact 下载与核对 | 两项 artifact 已下载；核对 368 项文件，保存 369 文件的完整下载目录备份；PR head 与 artifact 检出版本分开记录 | [核对结果](evidence/ci/verification.json)、[CI 下载备份](evidence/pr6-ci-evidence.tar.gz)、[校验值](evidence/SHA256SUMS) |

服务器容器中的主要测试命令为 `python3 -m unittest test_profile.Student241880546E10Tests -v` 和 `python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v`；完整容器参数见 [个人报告](个人报告.md)。

## 参考实现与个人贡献边界

课程和队友已有的 `fixture / scan / patch / validate / buildchecker`、共享修复扩展及原 21 项测试均保持其原有归属。本人新增 1 项编译失败拒绝回归测试，完成个人 E8/E9 基础流程与 E10 运行和证据整理；E8/E9 未新增个人自主扩展，不声称独立实现整个 MDFixer 算法。

本人 E10 未调用在线模型生成论文式修复候选：正常候选来自课程显式规则逻辑，负面候选来自预设的非法编译参数。
