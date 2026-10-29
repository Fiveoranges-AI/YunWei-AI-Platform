import { readFile } from "node:fs/promises";
const templateUrl = new URL("../templates/demo.html", import.meta.url);
const messagesUrl = new URL("../templates/demo.messages.json", import.meta.url);
export async function renderDemo(locale) {
  const template = await readFile(templateUrl, "utf8");
  const messages = JSON.parse(await readFile(messagesUrl, "utf8"));
  const home = locale === "en" ? "/" : "/zh/";
  const zh = locale === "zh-CN";
  return template
    .replace(/\{\{(\w+)\}\}/g, (_, key) => {
      if (!messages[key]?.[locale])
        throw new Error(`Missing demo message: ${key}/${locale}`);
      return messages[key][locale];
    })
    .replace('<html lang="zh-CN">', `<html lang="${locale}">`)
    .replaceAll('href="/"', `href="${home}"`)
    .replaceAll(
      "window.location.href = '/'",
      `window.location.href = '${home}'`
    )
    .replaceAll(
      'href="/strategy-call"',
      `href="${zh ? "/zh" : ""}/strategy-call"`
    )
    .replace(
      '<div class="actions">',
      `<div class="actions"><select id="demo-language" aria-label="${zh ? "选择语言" : "Choose language"}" style="min-height:44px;max-width:110px;border:1px solid #E2E8F0;border-radius:8px;color:#0F2340;background:white"><option value="en" ${!zh ? "selected" : ""}>English</option><option value="zh-CN" ${zh ? "selected" : ""}>简体中文</option></select>`
    )
    .replace(
      '<div class="thread-wrap" id="thread-wrap">',
      `<div class="thread-wrap" id="thread-wrap"><p role="note" style="padding:12px 20px;margin:0;background:#EEF4FB;color:#1F4F7A;font-size:13px">${zh ? "交互演示 · 全部为虚构示例数据；名称不代表客户关系或背书。按钮用于重放示例，不接入真实 ERP、不发送消息。" : "Interactive illustration · Fictional sample data. No customer relationship, endorsement, or live ERP connection is implied. Controls replay a sample scenario."}</p>`
    )
    .replace(
      "/* ============ Wire up ============ */",
      `document.getElementById('demo-language').addEventListener('change', e => { const next = e.target.value; try { localStorage.setItem('fiveoranges.locale.v1', next); } catch {} window.location.assign((next === 'en' ? '/demo.html' : '/zh/demo.html') + window.location.search + window.location.hash); });`
    )
    .replace(
      "</style>",
      `a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #2D6EA8;outline-offset:3px} .main,.crumbs{min-width:0} .thread-wrap{display:block} .thread{margin-inline:auto} .thread-wrap>[role=note]{max-width:760px;margin:0 auto 20px!important;box-sizing:border-box} .topbar{flex-wrap:wrap;height:auto;min-height:64px;gap:8px;padding-top:8px;padding-bottom:8px} .actions{flex-wrap:wrap} @media(max-width:600px){.topbar .title{font-size:14px}.topbar .actions{gap:4px}.topbar .icn-btn{width:36px;height:44px}.topbar .home{min-height:44px}.table-wrap{overflow-x:auto}.composer-disclaim{line-height:1.5}.stage{max-width:100vw}} @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}</style>`
    );
}
