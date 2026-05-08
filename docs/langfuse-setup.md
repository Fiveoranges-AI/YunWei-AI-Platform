# Langfuse Cloud 起手指南

> **Status**: draft, 2026-05-05
> **Purpose**: 起 Langfuse 项目最低门槛路径,**0 月费**(50k events 免费 tier),验证 kernel `pull-langfuse-badcase` + production trace 回流真链路。
> **Counterpart**: kernel side at `YunWei-AI-Kernel/kernel/telemetry/{langfuse_client,langfuse_writer}.py`

## 决策路径

我们之前(spec §17 Q1)决议 "**cloud 起手,self-host 留 v2**"。本文档执行 cloud 起手部分。后续 self-host 迁移走单独 spec。

不选 Mac mini 自托管的原因(2026-05-05 确认):家庭运营商 + CF Tunnel 不靠谱(运营商可能阻塞 / IP reputation / 高峰期不稳),Langfuse 作为生产 telemetry 必须高可用。

## Step 1: 注册 Langfuse Cloud

打开 [https://cloud.langfuse.com](https://cloud.langfuse.com) 选区域:

| 区域 | 域名 | 适用 |
|---|---|---|
| **EU**(默认推荐) | `https://cloud.langfuse.com` | 国际客户 |
| **US** | `https://us.cloud.langfuse.com` | 美国客户为主 |

**国内客户访问延迟**:EU ~250ms,US ~200ms。能用,但慢。后续要中国机房就走自托管(腾讯云轻量服务器或阿里云)。

注册账号(GitHub OAuth 最快)。免费 tier 给 50k events / month —— SME 单租户每天 100-500 trace 用半年才到上限。

## Step 2: 创建组织 + 项目

- 组织名:`yunwei` 或 `fiveoranges`
- 项目名:**每个 tenant 一个**(spec §15 隔离原则:跨租户不共享 search-set / candidate / pattern)
  - 起步:`yinhu-prod`(银湖生产)、`yinhu-dev`(银湖开发,可选)
  - 第 2 客户加入时:再建一个项目

## Step 3: 拿 API Keys

进入项目 → Settings → **API Keys** → Create new API keys

复制三件:
- `LANGFUSE_HOST`(就是项目 URL,如 `https://cloud.langfuse.com`)
- `LANGFUSE_PUBLIC_KEY`(`pk-lf-...`)
- `LANGFUSE_SECRET_KEY`(`sk-lf-...`)

**保管**:secret key 只显示一次,丢了就重生成。建议存在:
- 你的 1Password / Bitwarden(主源)
- `/Users/eason/agent-platform/.env`(平台进程 runtime 注入,gitignored)
- 你 macOS Keychain(可选备份)

## Step 4: kernel 端验证(opt-in 集成测试)

把 keys 临时塞进你 shell:

```bash
export LANGFUSE_HOST=https://cloud.langfuse.com
export LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
export LANGFUSE_SECRET_KEY=sk-lf-yyyyyyyy
```

然后在 kernel repo 跑集成测试:

```bash
cd /Users/eason/Documents/eason/five-oranges/YunWei-AI-Kernel
python3 -m pytest tests/integration/test_langfuse_real.py -v
```

期待:**3 测试 pass**(写测试 trace → 拉回来 → 比对 trace_id)。如果 401 就是 keys 错;如果 timeout 就是网络。

## Step 5: production agent 接入(yinhu / 未来 generated agent)

production agent 容器需要 dual-write:本地 fallback(主)+ Langfuse(派生)。kernel side 提供 `kernel/telemetry/langfuse_writer.py` 做 best-effort SDK 写。

yinhu 当前的 web_agent.py **还没接入**——这是单独的 task,见 platform v2.0 升级。新 generated agent 出厂自带 dual-write(spec §4.6)。

最小集成代码(production 容器 entrypoint):

```python
# 容器启动时注入
import os
from langfuse import Langfuse  # pip install langfuse>=3
lf = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ["LANGFUSE_HOST"],
)

# 每条对话起 trace
trace = lf.trace(name="boss-query", user_id=username, metadata={...})
gen = trace.generation(name="agent-loop", model="claude-haiku-4-5")
# ...生成响应...
gen.end(output=final_text, usage={"input": ..., "output": ...})
```

完整接入设计走 platform v2.0 spec(独立工作)。

## Step 6: 容器环境变量注入

production docker-compose.yml(yinhu / 未来 agents)加:

```yaml
services:
  agent-yinhu-super-xiaochen:
    image: yunwei/agent-yinhu:latest
    env_file:
      - .env.langfuse  # gitignored
    environment:
      LANGFUSE_HOST: ${LANGFUSE_HOST}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
```

平台启动脚本读 `.env.langfuse` 或从 1Password CLI 注入。

## Step 7: 验证生产链路

部署后:
1. 打开 `https://app.fiveoranges.ai/c/yinhu/super-xiaochen` 跟 agent 对话几句
2. 切换到 `https://cloud.langfuse.com` 项目页 → Traces,应能看到刚刚的对话
3. kernel 端执行 `yunwei harness pull-langfuse --hours 1`,应能拉到这些 trace 进 `runtime-telemetry/`

到这一步 M3 真闭环就跑通了。

## Pricing 心算

50k events 免费 → 每对话约 5-10 events(prompt + tool_call + tool_result + model_response + task_done)→ **5000-10000 对话 / 月免费**。
- 银湖 1 个老板,每天问 10 次 = 300 对话/月,~3k events,远远没事
- 第 2 客户加进来到第 5 客户:还是没事
- 第 10 客户起想付费版:$59/月起,或者**那时候迁自托管**

## 回退路径

如果 Langfuse Cloud 出问题(墙了 / 涨价 / SLA 差):
1. 本机 fallback 主源仍在(`runtime-telemetry/local-trace-fallback-*.jsonl`),production 不挂
2. 数据导出:Langfuse 官方有 `langfuse export` CLI,导出全部历史
3. 自托管迁移:跑一份 v2/v3 docker-compose,导入数据(走 self-host 单独 spec)

kernel `pull-langfuse-badcase` 设计就吃了这点(spec §4.6):**local 主,Langfuse 派生**,Langfuse 不可达时 soft-fail 用本地数据,不影响 Meta-Harness 闭环。

## 已决议(本文档落地后无需再决)

- ✅ Langfuse Cloud 起手 v0(本文)
- ✅ EU 区域(国际优先,中国可接受)
- ✅ 每 tenant 一个 project
- ✅ 凭据走 platform `.env.langfuse`(gitignored)+ docker compose env_file 注入

## 仍开放(后续 spec 决)

- self-host 迁移触发条件(数据量阈值?延迟阈值?客户合规要求?)
- yinhu web_agent.py 接入 Langfuse SDK 的具体 PR(需 platform v2.0 协调)
- 未来 generated agent 模板默认包含 Langfuse SDK 注入点
