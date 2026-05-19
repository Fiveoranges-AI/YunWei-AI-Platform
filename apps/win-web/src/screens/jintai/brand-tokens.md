# 锦泰品牌 tokens 抓取（来自 kamtai.cc，Iter 14）

> 仅作 design reference 不入运行时代码。`--jintai-*` CSS vars 在 `tokens.css` / `JintaiHero.tsx` inline 注入。

## 主色（确认抓取值）

| Token | Hex | 来源 |
|---|---|---|
| `--jintai-red` | `#C32629` | active nav link 颜色 / section title「车间环境 / 新闻资讯」/ 序号 03 红方块 / 大量 emphasis 位 |
| `--jintai-red-50` | `#FBE9E9` (估算) | section 红淡色 hover / badge bg |
| `--jintai-green` | `#1B7F3A` | logo 草字头叶子（estimated，按 user spec） |
| `--jintai-gold` | `#C9962E` (估算) | Hero 装饰山脉 + "JIN TAI" 大英文字 |

## 灰阶与背景

- body 字色：`rgb(0, 0, 0)` 纯黑
- body 背景：透明（hero 红底覆盖 + 中段浅灰 section 分隔）
- section 浅灰背景：约 `#F5F6F8`
- 大字英文水印（WORKSHOP / NEWS CENTER）：浅灰 `#E5E5E7`

## 字体

```
font-family: sans-serif, "Microsoft Yahei", "Hiragino Sans GB",
             "Microsoft Sans Serif", "WenQuanYi Micro Hei";
```

system Chinese font stack，无 web font 引入。

## 视觉节奏

- **圆角**：`border-radius: 0px`（全直角，工业风）
- **section title 字号**：30-36 px，红色 #C32629
- **正文**：16px / 400 weight / 黑字
- **section 间距**：宽松留白（约 80-120px vertical padding）
- **网格**：3 列产品图 grid，间距均等，无阴影无圆角
- **CTA 按钮**：未明显，nav 文字 hover 红下划线

## 行业惯用元素

- Hero：大红底 + 金色山脉/英文水印「JIN TAI」+ 印章感 "锦泰" 二字 → 中国工业品牌经典构成
- 主页内容：车间实拍照 / 产品工艺照（耐火砖 / 承烧板 / 推板）
- 售后服务：3 步骤 「01 ... 02 ... 03 完善的售后服务体系」用红数字方块

## demo 注入策略（不破坏 iter 7 简洁 + 不换主色）

**保留**：智通客户产品 `--brand-500` 蓝色为主色（不能换）。

**注入位置（≤ 7 处）**：

1. Hero 顶部 3px 装饰条 `linear-gradient(90deg, jintai-red 0% 38%, transparent 38% 62%, jintai-green 62% 100%)`
2. Hero 右上角"锦泰定制版 v2026.05 · 发布于 2026-05-17"小字 + jintai-green 色
3. Hero 标题"宜兴市锦泰耐火材料"行 加 jintai-red 左侧 2px border + 黑字加粗
4. 财务 / 采购 AI 草稿提示条「✓ 王会计/张主管 复核确认」前加 jintai-green 圆点
5. 经营日报 AI 草稿条「✓ 许总 ... 已标已处理」同样加 jintai-green 圆点
6. footer 改为「Powered by 智通 AI · © 2026 Five Oranges AI · 为 宜兴市锦泰耐火材料 定制」+ 16px logo
7. Hero 既有 56px logo 保留（已是锦泰元素，不动）

**不做的**：
- 不换 nav 蓝色为红
- 不把全局按钮改为红填充
- 不引锦泰金色（demo 已有 AI 蓝 + brand 蓝 + ok 绿 + warn 琥珀 + risk 红，再加金色会色板过载）
- 不强行直角 — 卡片 8-12px 圆角是 iter 7 简洁基线，与锦泰直角调和：accent 是红绿点缀而非整体改造
