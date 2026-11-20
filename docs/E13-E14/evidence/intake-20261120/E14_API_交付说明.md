# B08 E14 四服务任务 API 交付

| 项目 | 记录 |
| --- | --- |
| 负责人 | 成员 3 滕明杰（241880546） |
| 分支 | `student/241880546/e14-integration` |
| 源码 SHA | `7b7e67b6c005bdf27ca7645790d75623230c00fe` |
| 父提交 | `9ec1f53429116fc3a1da60f4cac0388fe86023bd` |
| bundle | [B08-E14-API-241880546-7b7e67b.bundle](B08-E14-API-241880546-7b7e67b.bundle) |
| bundle SHA-256 | `dbafc6b75b58e59e7edd139f62a9a3e4cf5cf957423b4b94706977c7d827c4fc` |
| 交付状态 | 本地提交，完整历史 bundle 已验证，课程服务器实跑待验收 |

本次增加 E14 外层任务入口、测试和调用说明，并让四服务编排器接收该入口签发的 job/trace。已有 Compose 文件、角色服务及运行层沿用 `9ec1f53` 的字节。E13 G2 继续按已签收的 `ac923c516129d863346710ce029d37b12ea8336c` 登记。

## 恢复后核对输入

在 bundle 及其 [SHA-256](B08-E14-API-241880546-7b7e67b.bundle.sha256) 所在目录执行。使用新的检出目录。

```bash
set -e
sha256sum -c B08-E14-API-241880546-7b7e67b.bundle.sha256
git clone --branch student/241880546/e14-integration \
  B08-E14-API-241880546-7b7e67b.bundle e14-api-7b7e67b
test "$(git -C e14-api-7b7e67b rev-parse HEAD)" = 7b7e67b6c005bdf27ca7645790d75623230c00fe
```

继续使用现有[彩排输入包](../../../e14_coordination_241880546/handoff-vjd7ggzu/B08-E14-rehearsal-source.zip)中的 `inputs/` 和 `requests/`，按包内说明恢复到新检出的 `data/`。该 ZIP 的 SHA-256 为 `24f62182b4871ffeab42f7c9559bd6710d42bec2ce23ddb5fccd6e617ead2364`。检出的新提交已包含四服务接线，恢复时仅执行输入准备部分。

| 样例 | profile | 请求 |
| --- | --- | --- |
| HeaderFlow | `explicit` | `requests/HeaderFlow-e14.json` |
| TinyExpr | `tinyexpr` | `requests/TinyExpr-e14.json` |

两套请求已在恢复后的仓库验过输入路径、候选 SHA-256 和 base/target 祖先关系。TinyExpr 检测器已核对为 `8355af8e45623855c3397442598bd07e27f1ec1a`。提交前通过 8 项 E14 测试和 26 项既有回归，从 bundle 恢复后再次通过 8 项 E14 测试。Docker 执行在这些测试中使用模拟实现。

## 课程服务器验收

1. 成员 1 复核 AMD64 承载镜像及端口占用，选用独立 Compose 项目。角色健康检查对应 `127.0.0.1:18181–18184`，任务 API 默认用 `127.0.0.1:18594`。Compose 的仓库挂载和 API 从同一份新检出的源码启动。
2. 按 bundle 中的 `docs/E13-E14/成员3-E14任务API.md` 启动 API。依次提交 HeaderFlow 和 TinyExpr，保存真实请求、任务终态、五阶段清单和下载记录。核对 job/trace、实际 DRAFT 镜像 ID、修复后的 `MISSING=0` 和原项目保护记录。
3. 用一份独立请求制造受控构建超时，保留本轮日志和清理核验；然后用新的幂等键启动恢复任务。记录故障任务与恢复任务各自的 job/trace，以及 API 下载后的 SHA-256。采集完成后按本次独立 Compose 项目名关闭服务。
4. 成员 4 按完整源码 SHA 登记课程服务器原件、后续 CI 和 E14 门禁结论。
