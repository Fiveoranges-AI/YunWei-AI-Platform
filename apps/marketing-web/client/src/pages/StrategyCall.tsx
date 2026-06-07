/* =============================================================
   Strategy Call — 预约30分钟AI数字化诊断 (v1.3)
   Low-risk intake page for manufacturing SME owners. The form is
   fully client-side: on submit it assembles a pre-filled email to
   fiveorangesltd@gmail.com (no backend required), so nothing is lost
   if no mail server is wired up.
   ============================================================= */

import { useEffect, useState } from "react";
import type { ChangeEvent, Dispatch, FormEvent, SetStateAction } from "react";
import { ArrowRight, Check, CheckCircle2, Clock, Mail, ShieldCheck } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const CONTACT_EMAIL = "fiveorangesltd@gmail.com";

const seo = {
  title: "预约30分钟AI数字化诊断 | Five Oranges AI / 运帷AI",
  description:
    "面向制造业、贸易与中小企业的低风险 AI 数字化诊断。如果你正面对库存不准、订单进度不透明、客户资料分散、Excel 管理混乱、ERP 太复杂或不知道如何用 AI，可预约一次 30 分钟战略沟通。",
  keywords:
    "AI数字化诊断, 制造业AI数字化, 库存管理AI, 中小企业数字化升级, 轻量化ERP, CRM客户管理, 战略沟通, Five Oranges AI, 运帷AI",
};

const PROBLEM_OPTIONS = [
  "库存不准",
  "订单进度不透明",
  "客户资料分散",
  "Excel 管理混乱",
  "ERP 太复杂 / 不好用",
  "想用 AI 但不知道从哪里开始",
  "其他",
];

const SYSTEM_OPTIONS = ["Excel", "金蝶 / 用友", "ERP", "CRM", "自研系统", "还没有系统"];

const SIZE_OPTIONS = ["1–20 人", "20–50 人", "50–200 人", "200 人以上"];

const VALUE_POINTS = [
  "针对你最痛的 1 个场景，给出可落地的 AI 改造方向",
  "判断是做轻量化系统，还是与现有 ERP / CRM 集成",
  "一个从小范围验证开始的起步建议，避免大投入试错",
  "诚实评估：AI 是否真的适合你的企业现在做",
];

type Field = "name" | "company" | "industry" | "size" | "goal" | "contact" | "note";

function useSeoMetadata() {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = seo.title;

    const upsertMeta = (attribute: "name" | "property", key: string, content: string) => {
      let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      if (!tag) {
        tag = document.createElement("meta");
        tag.setAttribute(attribute, key);
        document.head.appendChild(tag);
      }
      const previous = tag.getAttribute("content");
      tag.setAttribute("content", content);
      return () => {
        if (previous === null) tag?.remove();
        else tag?.setAttribute("content", previous);
      };
    };

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    const previousCanonical = canonical?.getAttribute("href");
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      document.head.appendChild(canonical);
    }
    canonical.setAttribute("href", "https://fiveoranges.ai/strategy-call");

    const cleanup = [
      upsertMeta("name", "description", seo.description),
      upsertMeta("name", "keywords", seo.keywords),
      upsertMeta("property", "og:title", seo.title),
      upsertMeta("property", "og:description", seo.description),
      upsertMeta("property", "og:url", "https://fiveoranges.ai/strategy-call"),
      upsertMeta("property", "og:type", "website"),
      upsertMeta("name", "twitter:title", seo.title),
      upsertMeta("name", "twitter:description", seo.description),
    ];

    return () => {
      document.title = previousTitle;
      cleanup.forEach((fn) => fn());
      if (previousCanonical === undefined) canonical?.remove();
      else if (previousCanonical === null) canonical?.removeAttribute("href");
      else canonical?.setAttribute("href", previousCanonical);
    };
  }, []);
}

function toggle(
  setList: Dispatch<SetStateAction<string[]>>,
  value: string,
) {
  setList((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
}

export default function StrategyCall() {
  useSeoMetadata();

  const [form, setForm] = useState<Record<Field, string>>({
    name: "",
    company: "",
    industry: "",
    size: "",
    goal: "",
    contact: "",
    note: "",
  });
  const [problems, setProblems] = useState<string[]>([]);
  const [systems, setSystems] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const setField =
    (key: Field) =>
    (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));

  const buildMailto = () => {
    const lines = [
      `姓名：${form.name}`,
      `公司名称：${form.company}`,
      `行业：${form.industry}`,
      `企业规模：${form.size}`,
      `当前最希望改善的问题：${problems.join("、")}`,
      `目前使用系统：${systems.join("、")}`,
      `希望解决目标：${form.goal}`,
      `联系方式：${form.contact}`,
      `补充说明：${form.note}`,
    ];
    const subject = `AI 数字化诊断预约 — ${form.company || form.name || "新咨询"}`;
    const body = `我想预约一次 30 分钟 AI 数字化诊断，以下是我的情况：\n\n${lines.join("\n")}\n`;
    return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.name.trim() || !form.contact.trim()) {
      setError("请至少填写姓名和联系方式，方便我们与你确认时间。");
      return;
    }
    setError("");
    window.location.href = buildMailto();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        {/* Header */}
        <section className="strategy-hero">
          <div className="container">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              AI 数字化诊断 · STRATEGY CALL
            </span>
            <h1 className="strategy-title">预约30分钟AI数字化诊断</h1>
            <p className="strategy-subtitle">
              如果你的企业正在面对库存、订单、客户管理、ERP、CRM 或 AI
              落地问题，可以先预约一次低风险的战略沟通。
            </p>
            <div className="strategy-trust-row">
              {["低风险沟通，不收费", "不推销复杂系统", "聚焦你最痛的场景"].map((t) => (
                <span key={t} className="strategy-trust-chip">
                  <Check size={14} strokeWidth={2.5} aria-hidden />
                  {t}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* Body */}
        <section className="strategy-body">
          <div className="container">
            <div className="strategy-grid">
              {/* Left — value + trust */}
              <aside className="strategy-aside">
                <div className="strategy-aside-block">
                  <div className="strategy-aside-eyebrow">
                    <Clock size={16} strokeWidth={2.1} aria-hidden />
                    这 30 分钟里，你会得到
                  </div>
                  <ul className="strategy-value-list">
                    {VALUE_POINTS.map((p) => (
                      <li key={p}>
                        <CheckCircle2 size={18} strokeWidth={2} aria-hidden />
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="strategy-lowrisk">
                  <ShieldCheck size={18} strokeWidth={2} aria-hidden />
                  <p>
                    这是一次<strong>低风险的战略沟通</strong>，不收费、不推销复杂系统。你提供的信息仅用于本次沟通准备，不会用于其他用途。
                  </p>
                </div>

                <div className="strategy-direct">
                  不想填表？直接邮件我们：
                  <a href={`mailto:${CONTACT_EMAIL}`} className="strategy-direct-link">
                    {CONTACT_EMAIL}
                  </a>
                </div>
              </aside>

              {/* Right — intake form */}
              <div className="strategy-form-card">
                <form onSubmit={handleSubmit} noValidate>
                  <div className="sc-row">
                    <div className="sc-field">
                      <label className="sc-label" htmlFor="sc-name">
                        姓名 <span className="sc-req">*</span>
                      </label>
                      <input
                        id="sc-name"
                        className="sc-input"
                        type="text"
                        autoComplete="name"
                        placeholder="您的称呼"
                        value={form.name}
                        onChange={setField("name")}
                      />
                    </div>
                    <div className="sc-field">
                      <label className="sc-label" htmlFor="sc-company">
                        公司名称
                      </label>
                      <input
                        id="sc-company"
                        className="sc-input"
                        type="text"
                        autoComplete="organization"
                        placeholder="企业名称"
                        value={form.company}
                        onChange={setField("company")}
                      />
                    </div>
                  </div>

                  <div className="sc-row">
                    <div className="sc-field">
                      <label className="sc-label" htmlFor="sc-industry">
                        行业
                      </label>
                      <input
                        id="sc-industry"
                        className="sc-input"
                        type="text"
                        placeholder="如：注塑 / 五金 / 贸易 / 仓储"
                        value={form.industry}
                        onChange={setField("industry")}
                      />
                    </div>
                    <div className="sc-field">
                      <label className="sc-label" htmlFor="sc-size">
                        企业规模
                      </label>
                      <select
                        id="sc-size"
                        className="sc-input sc-select"
                        value={form.size}
                        onChange={setField("size")}
                      >
                        <option value="">请选择</option>
                        {SIZE_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="sc-field">
                    <span className="sc-label">当前最希望改善的问题</span>
                    <div className="sc-chip-group">
                      {PROBLEM_OPTIONS.map((opt) => {
                        const on = problems.includes(opt);
                        return (
                          <button
                            type="button"
                            key={opt}
                            className={`sc-chip${on ? " sc-chip-on" : ""}`}
                            aria-pressed={on}
                            onClick={() => toggle(setProblems, opt)}
                          >
                            {on && <Check size={14} strokeWidth={2.6} aria-hidden />}
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="sc-field">
                    <span className="sc-label">目前使用系统</span>
                    <div className="sc-chip-group">
                      {SYSTEM_OPTIONS.map((opt) => {
                        const on = systems.includes(opt);
                        return (
                          <button
                            type="button"
                            key={opt}
                            className={`sc-chip${on ? " sc-chip-on" : ""}`}
                            aria-pressed={on}
                            onClick={() => toggle(setSystems, opt)}
                          >
                            {on && <Check size={14} strokeWidth={2.6} aria-hidden />}
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="sc-field">
                    <label className="sc-label" htmlFor="sc-goal">
                      希望解决目标
                    </label>
                    <textarea
                      id="sc-goal"
                      className="sc-input sc-textarea"
                      rows={3}
                      placeholder="例如：让库存账实一致、订单进度能实时看到、客户资料统一管理……"
                      value={form.goal}
                      onChange={setField("goal")}
                    />
                  </div>

                  <div className="sc-field">
                    <label className="sc-label" htmlFor="sc-contact">
                      联系方式 <span className="sc-req">*</span>
                    </label>
                    <input
                      id="sc-contact"
                      className="sc-input"
                      type="text"
                      placeholder="微信 / 邮箱 / 电话"
                      value={form.contact}
                      onChange={setField("contact")}
                    />
                  </div>

                  <div className="sc-field">
                    <label className="sc-label" htmlFor="sc-note">
                      补充说明
                    </label>
                    <textarea
                      id="sc-note"
                      className="sc-input sc-textarea"
                      rows={2}
                      placeholder="任何想让我们提前了解的情况（可选）"
                      value={form.note}
                      onChange={setField("note")}
                    />
                  </div>

                  {error && (
                    <p className="sc-error" role="alert">
                      {error}
                    </p>
                  )}

                  <button type="submit" className="sc-submit hover-lift">
                    <Mail size={17} strokeWidth={2.1} aria-hidden />
                    发送至 {CONTACT_EMAIL}
                    <ArrowRight size={16} strokeWidth={2.2} aria-hidden />
                  </button>

                  {submitted ? (
                    <p className="sc-hint" role="status">
                      已为你打开邮件应用并自动整理好内容。如果没有自动弹出，请直接发送至{" "}
                      <a href={`mailto:${CONTACT_EMAIL}`} className="strategy-direct-link">
                        {CONTACT_EMAIL}
                      </a>
                      ，我们会尽快与你确认时间。
                    </p>
                  ) : (
                    <p className="sc-hint">
                      点击后将打开你的邮件应用，内容已自动整理好，你确认后发送即可。
                    </p>
                  )}
                </form>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
