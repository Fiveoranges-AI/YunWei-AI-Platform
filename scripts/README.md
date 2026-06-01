# Demo 启动速查表（锦泰 / 光天）

> 白屏 99% 是 dev server 被笔记本休眠 / 关终端杀掉了。下面任一行重启即可。
> 纯 SQLite，无 docker / PG。失败先看对应 `/tmp/*.log`。

| 想做什么 | 一行命令 |
|---------|---------|
| **只启锦泰** | `bash scripts/jintai/start-demo.sh` |
| **只启光天** | `bash scripts/guangtian/start-demo.sh` |
| **两个一起启**（推荐） | `bash scripts/start-platform.sh` |
| **公开给 Tailscale/LAN 对端看** | `bash scripts/start-platform.sh --public` |
| **停掉**（按你启的那个） | `bash scripts/jintai/start-demo.sh stop` / `…/guangtian/… stop` / `bash scripts/start-platform.sh stop` |
| **失败看日志** | `tail -40 /tmp/jintai-demo-backend.log` · `tail -40 /tmp/guangtian-demo-backend.log` · `tail -40 /tmp/platform-*.log` |

## 打开地址

- 锦泰：`http://127.0.0.1:5175/win/?tab=jintai`（默认 mock）/ `…?tab=jintai&mode=backend&inspect=1`（真后端）
- 光天：`http://127.0.0.1:5175/win/?tab=guangtian`（默认 mock）/ `…?tab=guangtian&mode=backend&inspect=1`（真后端）

## 端口约定

| | 单独脚本 | `start-platform.sh`（两个并行） |
|---|---|---|
| 锦泰后端 | :8000 | :8000 |
| 光天后端 | :8000 | **:8001** |
| 前端 vite | :5175 | :5175 |

单独脚本各用 :8000，**不能同时跑两个 backend mode**（端口冲突）；要两个真后端同时在线就用 `start-platform.sh`（它给前端注入 `VITE_JINTAI_BACKEND` / `VITE_GUANGTIAN_BACKEND` 分别指向两端口）。mock 模式两个 tab 随时都能看，不依赖后端。

## 公开模式 `--public`（让赵博士通过 Tailscale 看）

```bash
bash scripts/start-platform.sh --public   # vite 绑 0.0.0.0
bash scripts/start-platform.sh            # 默认私有 (127.0.0.1, 仅本机)
```

- `--public` 只把 **vite** 绑到 `0.0.0.0:5175`；**两个后端仍只在 `127.0.0.1`**（不暴露）。
- demo 默认是 **mock 模式**（不调后端），所以远端访客直接看到完整演示，**不需要后端**。脚本结尾会打印 Tailscale IP + 完整 URL（如 `http://<ts-ip>:5175/win/?tab=jintai`）。
- 赵博士：装 Tailscale 进同一 tailnet → 打开 `http://<老板-mac-tailscale-ip>:5175/win/?tab=jintai`（或 `?tab=guangtian`）。
- 切私有/公开要先 `stop` 再换模式起（脚本对已在跑的 vite 会"放过不动"）。

### ⚠ 安全
- `0.0.0.0` 不止 Tailscale 可见，**同网段 LAN 也可见**。Tailscale 是私有 VPN、可控，但公共 WiFi 下 LAN 内别人也能打到 :5175。demo 数据无敏感信息，但**演示完 `bash scripts/start-platform.sh stop`**。
- `?mode=backend`（真后端 inspect 视图）**远端用不了**：后端故意没暴露，远端浏览器打 `127.0.0.1:8000` 是访客自己的机器。要远端也能看真后端数据，需给统一前端 `guangtian-frontend` 的 `vite.config.ts` 加 `/jintai-api`→:8000、`/guangtian-api`→:8001 代理（strip-prefix rewrite）+ 把 `VITE_*_BACKEND` 设成 `/jintai-api/api/win`、`/guangtian-api/api/win`（这样浏览器只跟 vite 同源说话、后端仍不暴露）。**本轮未做**：该 vite.config 在 `feat/guangtian-frontend-backend-mode`(#123) 分支,而该分支 local 与 origin 已分叉,贸然提交有 force-push 风险 → 留给老板定夺。

## 前提 / 排错

- **前端**走 `guangtian-frontend` worktree（同时带 jintai + guangtian 两 tab）。脚本会 probe：找不到含 `JintaiDemoPage.tsx` / `GuangtianDemoPage.tsx` 的 `apps/win-web` 就报错退出，不会起到错的（旧）前端白屏。
- **光天后端** `dev_guangtian_backend.py` 暂未进 main（PR #122 review 中），只在 `guangtian-backend` worktree → 脚本会 probe 到那。
- **python**：脚本会探测一个能 `import uvicorn` 的 python3（修过 round-25 的"裸 python3 没装包"坑）。找不到就 `pip3 install uvicorn fastapi sqlalchemy aiosqlite`，或 `JINTAI_PYTHON=/path/to/python3 bash …`。
- 可用 env override 路径：`DEMO_WEB_DIR` / `DEMO_BACKEND_DIR`（单独脚本）、`JINTAI_BACKEND_DIR` / `GUANGTIAN_BACKEND_DIR` / `DEMO_WEB_DIR`（unified）、`JINTAI_PYTHON` / `GUANGTIAN_PYTHON`。
</content>
