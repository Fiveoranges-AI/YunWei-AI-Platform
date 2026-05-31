import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { dailyReport } from "../data";
import { useGT } from "../state";

export function DailyReportPanel() {
  const isDesktop = useIsDesktop();
  const { showToast } = useGT();

  const onCopy = () => {
    const flatText = `${dailyReport.date} ${dailyReport.weekday} · 光天耐火 AI 库存日报\n\n${dailyReport.summary}\n\n${dailyReport.sections.map((s) => `${s.title}\n${s.items.map((i) => `  · ${i}`).join("\n")}`).join("\n\n")}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(flatText).then(
        () => showToast("✓ 日报全文已复制到剪贴板", "ok"),
        () => showToast("复制失败 · 请手动选择", "err"),
      );
    } else {
      showToast("✓ 日报全文已复制到剪贴板", "ok");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* AI 自动生成提示条 */}
      <div
        className="card"
        style={{
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
          background: "linear-gradient(120deg, var(--ai-50) 0%, #F8FAFF 100%)",
          borderLeft: "3px solid var(--ai-purple)",
        }}
      >
        <span
          style={{
            width: 30,
            height: 30,
            borderRadius: 8,
            background: "rgba(123,92,250,0.16)",
            color: "var(--ai-purple-deep)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {I.spark(15, "var(--ai-purple-deep)")}
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
            AI 已于 <span style={{ color: "var(--ai-purple-deep)" }}>{dailyReport.generatedAt}</span> 自动生成
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
            每天 18:30 准时生成 · 老板手机一键收
          </div>
        </div>
        <span
          style={{
            padding: "3px 10px",
            fontSize: 10.5,
            fontWeight: 700,
            borderRadius: 5,
            background: "rgba(27,127,58,0.10)",
            color: "var(--stock-ok)",
            border: "1px solid rgba(27,127,58,0.22)",
          }}
        >
          ✓ 数据完整
        </span>
      </div>

      {/* 日报正文 */}
      <article
        className="card"
        style={{
          padding: isDesktop ? "26px 30px" : "20px 18px",
          maxWidth: 880,
          width: "100%",
          alignSelf: "center",
        }}
      >
        {/* 报头 */}
        <header
          style={{
            paddingBottom: 16,
            marginBottom: 18,
            borderBottom: "2px solid var(--guangtian-red)",
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: "0.18em",
              color: "var(--guangtian-blue)",
              marginBottom: 6,
            }}
          >
            YIXING GUANGTIAN REFRACTORY · DAILY INVENTORY REPORT
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: isDesktop ? 26 : 22,
              fontWeight: 800,
              color: "var(--ink-900)",
              lineHeight: 1.25,
            }}
          >
            宜兴光天耐火 · <span style={{ color: "var(--guangtian-red)" }}>AI 库存日报</span>
          </h1>
          <div
            style={{
              marginTop: 8,
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontSize: 12.5,
              color: "var(--ink-600)",
            }}
          >
            <span style={{ fontWeight: 700, color: "var(--ink-800)" }}>{dailyReport.date}</span>
            <span style={{ color: "var(--ink-400)" }}>·</span>
            <span>{dailyReport.weekday}</span>
            <span style={{ color: "var(--ink-400)" }}>·</span>
            <span>陈总 / 仓库主管 · 内部参阅</span>
          </div>
        </header>

        {/* 摘要 */}
        <section
          style={{
            padding: "12px 14px",
            background: "var(--surface-2)",
            border: "1px solid var(--ink-100)",
            borderRadius: 10,
            marginBottom: 20,
          }}
        >
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--guangtian-red)", marginBottom: 6, letterSpacing: "0.02em" }}>
            📌 今日摘要
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--ink-800)", lineHeight: 1.75 }}>
            {dailyReport.summary}
          </p>
        </section>

        {/* 8 大块 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {dailyReport.sections.map((s, i) => (
            <ReportSection key={i} title={s.title} items={s.items} />
          ))}
        </div>

        {/* 报尾签名 */}
        <footer
          style={{
            marginTop: 26,
            paddingTop: 14,
            borderTop: "1px solid var(--ink-100)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 11,
            color: "var(--ink-500)",
            flexWrap: "wrap",
            gap: 8,
          }}
        >
          <span>本日报由 AI 库存管家 自动生成 · 数据来自仓储系统实时快照</span>
          <span style={{ fontFamily: "var(--font-mono, var(--font))" }}>
            v2026.05 · {dailyReport.generatedAt}
          </span>
        </footer>
      </article>

      {/* 底部操作 */}
      <div
        className="card"
        style={{
          padding: "14px 16px",
          maxWidth: 880,
          width: "100%",
          alignSelf: "center",
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 12, color: "var(--ink-500)", marginRight: 4 }}>分发：</span>
        <button style={ACTION_PRIMARY} onClick={onCopy}>📋 复制全文</button>
        <button
          style={ACTION_BLUE}
          onClick={() => showToast(`✓ PDF 生成中 · 文件名 光天日报_${dailyReport.date}.pdf`, "info")}
        >
          📄 导出 PDF
        </button>
        <button
          style={ACTION_WX}
          onClick={() => showToast("✓ 已通过企业微信发送给陈总 · 阅读时间 18:32", "ok")}
        >
          💬 发给陈总（微信）
        </button>
        <button
          style={ACTION_WX}
          onClick={() => showToast("✓ 已通过企业微信发送给王主管 · 阅读时间 18:32", "ok")}
        >
          💬 发给王主管（仓库主管）
        </button>
        <button
          style={ACTION_GHOST}
          onClick={() => showToast("打开日报模板编辑器（演示版本暂未实现）", "warn")}
        >
          修改模板
        </button>
      </div>
    </div>
  );
}

function ReportSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h3
        style={{
          margin: "0 0 8px",
          fontSize: 14.5,
          fontWeight: 700,
          color: "var(--ink-900)",
          paddingLeft: 10,
          borderLeft: "3px solid var(--guangtian-blue)",
          lineHeight: 1.3,
        }}
      >
        {title}
      </h3>
      <ul
        style={{
          margin: 0,
          paddingLeft: 22,
          fontSize: 12.5,
          color: "var(--ink-700)",
          lineHeight: 1.8,
          listStyle: "none",
        }}
      >
        {items.map((it, i) => (
          <li
            key={i}
            style={{
              position: "relative",
              paddingLeft: 8,
            }}
          >
            <span
              aria-hidden
              style={{
                position: "absolute",
                left: -10,
                top: 12,
                width: 4,
                height: 4,
                borderRadius: "50%",
                background: "var(--ink-300)",
              }}
            />
            {it}
          </li>
        ))}
      </ul>
    </section>
  );
}

const ACTION_PRIMARY: React.CSSProperties = {
  padding: "7px 13px",
  fontSize: 12.5,
  fontWeight: 600,
  borderRadius: 7,
  border: "none",
  background: "var(--guangtian-red)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

const ACTION_BLUE: React.CSSProperties = {
  ...ACTION_PRIMARY,
  background: "var(--guangtian-blue)",
};

const ACTION_WX: React.CSSProperties = {
  ...ACTION_PRIMARY,
  background: "var(--stock-ok)",
};

const ACTION_GHOST: React.CSSProperties = {
  padding: "7px 13px",
  fontSize: 12.5,
  fontWeight: 500,
  borderRadius: 7,
  border: "1px solid var(--ink-200)",
  background: "#fff",
  color: "var(--ink-700)",
  cursor: "pointer",
  fontFamily: "var(--font)",
};
