# 给成员 1／4：B08 E14 四服务彩排稿

此包是可重建的本地彩排工作稿。工具共同基线 `fcd36c0082be043c8fece6a61941321833171aa7` 用 `source/tools-paired.bundle` 恢复；实际改动为 `overlay/` 中的六个文件。`SOURCE_IDENTITY.json` 记录逐文件 SHA-256。**基线 SHA 不是接线稿的新 Git 提交；本稿未提交、无 PR、未在课程服务器部署。** 不作为最终版本或 CI 通过证据。

- 计划项目名 `b08-e14-member1-review`；BuildChecker、EChecker、DRAFT、MDFixer 分别用本机 `18181`、`18182`、`18183`、`18184`，编排和 Compose 已对齐。容器内仍为 `8080`，仅 DRAFT 挂载 Docker socket。
- 计划 Linux AMD64 承载镜像 `sha256:1fa773b9ed7fdf35281eda86ec53ebf61048f271a70a43f9ccfd0e2d7a759829`。它是本地镜像 ID，不是拉取地址。成员 1 的本机健康/重启证据不是课程服务器端口确认或任务恢复实测。
- `requests/HeaderFlow-e14.json`、`requests/TinyExpr-e14.json` 是各真实项目的彩排请求；各自使用 `inputs/` 的固定项目、DRAFT 候选和 TinyExpr 完整输出。G2 外部原报告消费另走 `e13-b`；不要把该回放冒充本轮四角色五阶段。

## 在全新目录恢复

将本包解压至只读输入目录，`PACK` 指向其绝对路径，`REPO` 指向一个不存在的新目录。先验证 ZIP 同名 SHA-256 及包内 `FILES.json`，不要在共同部署目录应用 overlay。

```bash
git clone --branch student/241880492/e13-e14-paired-acceptance "$PACK/source/tools-paired.bundle" "$REPO"
cd "$REPO"
test "$(git rev-parse HEAD)" = fcd36c0082be043c8fece6a61941321833171aa7
cp -a "$PACK/overlay/." .
mkdir -p data/headerflow data/tinyexpr data/tinyexpr-a-detector
git clone --branch e13e14/input-A-headerflow "$PACK/inputs/headerflow/project.bundle" data/headerflow/repo
git clone --branch course/e11-e12 "$PACK/inputs/tinyexpr/project.bundle" data/tinyexpr/repo
git -C data/tinyexpr-a-detector init
git -C data/tinyexpr-a-detector fetch --no-tags "$PACK/inputs/tinyexpr-detector.bundle" HEAD
git -C data/tinyexpr-a-detector checkout --detach 8355af8e45623855c3397442598bd07e27f1ec1a
cp "$PACK/inputs/headerflow/candidate.Dockerfile" data/headerflow/
cp "$PACK/inputs/tinyexpr/candidate.Dockerfile" "$PACK/inputs/tinyexpr/expected-stdout.txt" data/tinyexpr/
cp "$PACK/requests/HeaderFlow-e14.json" data/headerflow/
cp "$PACK/requests/TinyExpr-e14.json" data/tinyexpr/
```

## 上机要核对什么

先完成端口和镜像探测，确认项目名没有在用。用本次专属的服务根与镜像环境变量执行 `docker compose -p b08-e14-member1-review -f labs/e13e14/compose.yaml config --quiet`，核对后才启动。只关闭本次部署时，保留相同环境变量、项目名和 Compose 文件，执行 `docker compose -p b08-e14-member1-review -f labs/e13e14/compose.yaml down`。不要动旧服务或清理共享 Docker 资源。

先验固定样例，再跑两个真实请求；之后验证一次受控超时及新任务恢复。原始请求/响应、四角色日志、`execution-runtime.json` 和实际角色／项目镜像身份均要留档。外层 `/v1/jobs` 尚未切到四服务，不能把旧单容器 API 当作本稿验收结果。正式验收和发布仍等 E13 门禁通过及组内确认。
