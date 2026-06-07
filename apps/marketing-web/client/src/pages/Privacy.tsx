/* =============================================================
   Privacy Policy — /privacy
   Concise, professional privacy policy for a small AI consulting /
   digital-transformation company. Intentionally does NOT overclaim
   legal compliance (no GDPR/CCPA certification claims).
   ============================================================= */

import LegalPage from "@/components/LegalPage";

const seo = {
  title: "隐私政策 · Privacy | Five Oranges AI / 运帷AI",
  description:
    "Five Oranges AI / 运帷AI 隐私政策：我们收集哪些信息、如何使用、如何保护，以及你的权利。",
  keywords: "隐私政策, Privacy, Five Oranges AI, 运帷AI, 数据保护",
};

const EMAIL = "contact@fiveoranges.ai";

export default function Privacy() {
  return (
    <LegalPage
      seo={seo}
      path="/privacy"
      label="隐私政策 · PRIVACY"
      title="隐私政策"
      subtitle="我们尊重并努力保护你的隐私。本政策说明我们在你访问网站或与我们沟通时，如何收集、使用与保护信息。"
      updated="2026 年 6 月"
    >
      <h2>我们收集的信息</h2>
      <p>我们仅收集为提供咨询与沟通所必要的信息，主要包括：</p>
      <ul>
        <li>
          <strong>你主动提供的信息</strong>：当你通过预约表单或邮件与我们联系时填写的姓名、公司名称、行业、企业规模、联系方式及咨询内容。
        </li>
        <li>
          <strong>基本访问信息</strong>：浏览器类型、访问页面等用于了解网站使用情况的匿名统计数据。
        </li>
      </ul>

      <h2>信息如何使用</h2>
      <p>我们使用上述信息用于：</p>
      <ul>
        <li>回复你的咨询，并为战略沟通或诊断做准备；</li>
        <li>在你同意的范围内，提供与业务相关的方案建议；</li>
        <li>改进网站内容与服务质量。</li>
      </ul>
      <p>我们不会出售或出租你的个人信息。</p>

      <h2>信息共享</h2>
      <p>
        我们不会向无关第三方披露你的信息。仅在为完成你所请求的服务而确有必要时，才会与受保密义务约束的服务提供方共享最小必要信息；或在法律法规要求时依法配合。
      </p>

      <h2>数据安全</h2>
      <p>
        我们采取合理的技术与管理措施保护你的信息。关于我们在项目中如何处理企业数据，以及 AI 使用边界，详见
        {" "}
        <a href="/data-security">数据安全与 AI 使用边界</a>。
      </p>

      <h2>你的权利</h2>
      <p>
        你可以随时要求查询、更正或删除你提交给我们的个人信息。如需行使上述权利，请邮件联系{" "}
        <a href={`mailto:${EMAIL}`}>{EMAIL}</a>。
      </p>

      <h2>政策更新</h2>
      <p>我们可能不时更新本政策。更新后将在本页面公布最新版本与更新日期。</p>

      <h2>联系我们</h2>
      <p>
        如对本隐私政策有任何疑问，请联系{" "}
        <a href={`mailto:${EMAIL}`}>{EMAIL}</a>。
      </p>
    </LegalPage>
  );
}
