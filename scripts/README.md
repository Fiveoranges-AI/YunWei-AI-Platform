# Demo 启动速查表（锦泰 / 光天）

> 白屏 99% 是 dev server 被笔记本休眠 / 关终端杀掉了。下面任一行重启即可。
> 纯 SQLite，无 docker / PG。失败先看对应 `/tmp/*.log`。

| 想做什么 | 一行命令 |
|---------|---------|
| **只启锦泰** | `bash scripts/jintai/start-demo.sh` |
| **只启光天** | `bash scripts/guangtian/start-demo.sh` |
| **两个一起启**（推荐） | `bash scripts/start-platform.sh` |
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

## 前提 / 排错

- **前端**走 `guangtian-frontend` worktree（同时带 jintai + guangtian 两 tab）。脚本会 probe：找不到含 `JintaiDemoPage.tsx` / `GuangtianDemoPage.tsx` 的 `apps/win-web` 就报错退出，不会起到错的（旧）前端白屏。
- **光天后端** `dev_guangtian_backend.py` 暂未进 main（PR #122 review 中），只在 `guangtian-backend` worktree → 脚本会 probe 到那。
- **python**：脚本会探测一个能 `import uvicorn` 的 python3（修过 round-25 的"裸 python3 没装包"坑）。找不到就 `pip3 install uvicorn fastapi sqlalchemy aiosqlite`，或 `JINTAI_PYTHON=/path/to/python3 bash …`。
- 可用 env override 路径：`DEMO_WEB_DIR` / `DEMO_BACKEND_DIR`（单独脚本）、`JINTAI_BACKEND_DIR` / `GUANGTIAN_BACKEND_DIR` / `DEMO_WEB_DIR`（unified）、`JINTAI_PYTHON` / `GUANGTIAN_PYTHON`。
</content>
