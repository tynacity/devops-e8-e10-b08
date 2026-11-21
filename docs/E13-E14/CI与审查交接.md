# CI、审查与缺陷闭环交接

> 最新进展：[PR #17整合与main对齐](PR17整合与main对齐-20261121.md)。#14已合main、#15已关闭；#17已正式批准并合入共同分支aa274f3，本次同步main 8d6f4a4。下文保留此前时点记录；#16审查与最终发布配置仍待完成。

日期：2026-11-21；维护：成员4。

## 检查范围

| 检查名 | 责任与范围 |
| --- | --- |
| e7-b-quality-gate | 保留原E7门禁 |
| e8e10-quality-gate | 保留原E8–E10验证 |
| e11e12-integration | 保留契约及单入口固定样例五阶段 |
| e13-member4-preflight | 成员组件测试、公共报告拒绝、假值/扫描边界；增加完整检出历史与源码/历史扫描 |
| e14-compose-fixed-sample | 新增四容器固定样例正常、受控超时、新任务恢复；五阶段身份、产物字节/长度/SHA、报告/补丁哈希、各角色job/trace日志、实际镜像history/env与运行日志扫描 |

E14工作流只启动并关闭该次CI专属Compose项目；失败也留角色日志和产物。项目目录均新建，失败任务保留终态。此工作流不修改成员3的服务或编排代码，不宣称已经将新版MDFixer和TinyExpr接入四角色。

## 合并检查配置次序

1. 恢复GitHub认证后，先读取并保存当前main保护/ruleset、必需检查与审查设置；只增补检查，不覆盖其他保护。
2. 保留e7-b-quality-gate、e8e10-quality-gate。e11e12-integration已有main工作流，可在确认最新运行与权限后增补。
3. 本分支PR经复核且与组件PR的合入顺序明确后，将e13-member4-preflight、e14-compose-fixed-sample纳入本轮必需检查。避免让尚无这两个workflow的组件PR永久等待不存在的检查；需要时先将workflow带入对应PR分支。
4. 读取实际配置确认生效，核对PR提交对应全部检查。只从通过E13门禁且审查合并的提交选RC。

Windows用户环境已核对`gh api user=tynacity`；受限执行环境仍可能读取旧凭据并返回401，需要认证的gh操作使用已验证的Windows用户环境，不重复要求登录。此前缺少的CI附件已补取，原包保持不变，补件纳入本轮交付。

## 审查对象与贡献边界

共同分支：`student/241880492/e13-e14-paired-acceptance`；目标main。完整分支含成员1环境、成员2MDFixer与H2/C5、成员3e13-b报告入口及成员4验收/CI，保留原作者提交。

- [PR #14](https://github.com/tynacity/devops-e8-e10-b08/pull/14)仍是成员2组件交付入口。共同分支已包含其交付提交`efa63135f51bfed6d7047ae2de916ef80885ac07`；合入次序需与成员2/3对齐，不把共同分支里的他人实现记作成员4个人开发。
- 成员4新增：公共拒绝回归、输入与收件核对、独立API/C6证据、工作流与四服务固定样例CI、门禁汇总和发布准备。
- 成员3已回交旧输入C2/C3/C7/C8离线复核；成员2原四AMD64镜像C6复核、成员1 H2候选身份确认和部署补件已登记，见[11月19日接收记录](材料接收登记-20261119.md)。原C6缺失的三个附件已补齐；ARM64四服务任务恢复及AMD64拒绝后成功阶段证据已接收，见[本轮验收](四服务阶段证据验收-20261119.md)。H3、此前AMD64两镜像、G2及本轮三镜像/日志增量复核已全部接收；7b7e67b外层API真实项目验收已核验。材料回交不等同PR平台审批，未代签同伴审查。

## 已知缺陷

| Issue | 负责人/修复 | 失败与复测 | 当前关闭条件 |
| --- | --- | --- | --- |
| [#15 H2缺strace](https://github.com/tynacity/devops-e8-e10-b08/issues/15) | 成员2在PR #14交修订候选，成员1已确认修订哈希一致 | 工具06cfb71；原候选7bf4b0…，job-bb84b9934e1d4c2d8ed4a4b4e0c23c1c失败；修订f1e25df…，job-cfa2dc6672b841d2a8e0c85ad492756c五阶段通过。成员4已核对原始包 | 运行证据及候选身份确认已接收；待PR审查合并和相关验证，再由负责人关闭 |

H3原失败与修订成功证据及成员1发布候选确认已接收。[G2输入及C1–C3实跑](G2输入核对与C1-C3验收-20261119.md)已完成；G2新任务技术复核和双向签收登记已接收；H3/E14/G2已登记新增范围C6复核已全部接收；[正式四服务服务器证据](E14服务器正式验收-20261120.md)已核验。原阶段证据按原身份保留。11月20日已收9ec1f53六文件固定提交及其后续7b7e67b任务API提交，成员4独立验收分支的五类CI已通过；[固定版本与原始运行链接](正式源码与签收登记-20261120.md)单列，源码PR #17已建、目标为共同分支，push/PR十次CI通过但尚未审查合入；同SHA服务器真实项目原件已另行核验通过。G2本轮实际运行SHA为ac923c516129d863346710ce029d37b12ea8336c，材料登记提交不改变该身份。CI原始附件已归档；公开状态、原始产物和实际运行SHA分别保存。

## 本次独立验证与CI适配

服务器源码`e2d1813f179b9c7e0a8bc9db10f962dd70d4dcda`在独立目录`/root/241880492/e14-ci-20261118/repo`执行：正常与恢复任务均五阶段成功，超时任务内层TIMED_OUT、外层FAILED；162+36+162=360项产物字节/长度/SHA通过，四角色job/trace日志通过，当前3个实际镜像history/env及源码/历史、日志扫描通过。本次Compose已清理，原E12端口18546/18547均为200。见[云端摘要](evidence/ci-prep-20261118/cloud-acceptance.json)。

GitHub首次固定样例运行[44265595360](https://github.com/tynacity/devops-e8-e10-b08/actions/runs/44265595360)失败；添加诊断后的[44266547946](https://github.com/tynacity/devops-e8-e10-b08/actions/runs/44266547946)确认：宿主机runner用户创建项目副本，而四角色默认root，EChecker调用Git时因dubious ownership拒绝。服务器root/root环境未触发。

修复提交`5b4eff96449bcdb0ab96ebd88ba2d5fde22ce5c6`只在CI生成Compose覆盖配置：四角色使用宿主机UID/GID，DRAFT另外加入Docker socket的组。未关闭Git目录安全检查，未改成员1/3共享Compose、服务或编排算法。修复后实际CI结果随最终交付清单保存，失败记录保留。

普通用户模式进一步暴露Docker客户端默认写入`/.docker`的权限错误。隔离对照使用同一UID/GID、socket组和FROM scratch输入：默认HOME退出1，`HOME=/tmp`退出0；见[非root目录对照](evidence/ci-prep-20261118/nonroot-home-probe.json)。提交`3d9e09412b081aecc3543e4dda833de6ee66bacd`为CI角色增加可写HOME，沿用既有`run_e11e12.py`的容器环境约定。

## 当前远端与归档结果

程序提交`3d9e09412b081aecc3543e4dda833de6ee66bacd`五条CI全部成功，见[CI记录](evidence/ci-prep-20261118/ci-program.json)。新四服务CI的正常/超时/恢复共360项产物及4角色日志通过；镜像扫描范围见[CI摘要](evidence/ci-prep-20261118/github-compose-verification.json)。当前程序CI原始产物及两次已定位失败的原始包均已下载；也补齐上次3e388ec提交的四条CI附件。

经用户明确确认，main已仅增补`e11e12-integration`，现有E7/E8–E10、strict=true、管理员约束及其他保护保持不变；[修改前](evidence/ci-prep-20261118/protection-before.json)与[修改后](evidence/ci-prep-20261118/protection-after.json)已逐项核对。E13/E14两项暂未设为main全局必需检查：PR #14当前没有相应工作流，需先对齐组件PR与共同分支的合入次序。

平台当前required_approving_review_count为0；教师要求的PR审查仍需实际取得同伴记录，不因平台未强制审批而视为完成。此次未修改审查人数或合并main。

## 11月21日整合协调

[C6复核与PR #17登记](C6复核与PR17登记-20261121.md)已核验。#14当前head是两边祖先，离线合并无冲突，源码树相对固定7b7e67b不变。#17可现在转Ready并行审查；建议#14审查合main，随后#17审查合共同分支，核对整合CI，再完成#16审查合main。#14若新增提交，在#16最终CI前同步。平台Ready、人工review、合并和Issue关闭均仍待实际执行。

## 本轮审查记录已提交

[PR审查与收尾](PR审查与收尾-20261121.md)：成员4已对#14固定efa6313提交APPROVE，对仍Draft的#17固定7b7e67b提交COMMENT。两份回执已核对，未执行合并。dde29bf材料提交十次CI全部成功。#17转Ready后完成正式审批，合入后核对实际CI；#14新增提交时复核变化范围。
