/* =============================================================
   Terms of Use — /terms
   Standard website terms of use + service-inquiry disclaimer for a
   small AI consulting company. Not overclaiming; not legal advice.
   ============================================================= */

import LegalPage from "@/components/LegalPage";

const seo = {
  title: "服务条款 · Terms | Five Oranges AI / 运帷AI",
  description:
    "Five Oranges AI / 运帷AI 网站使用条款与咨询服务声明：网站内容用途、咨询性质、知识产权与责任限制。",
  keywords: "服务条款, Terms, 网站使用条款, Five Oranges AI, 运帷AI",
};

const EMAIL = "contact@fiveoranges.ai";

export default function Terms() {
  return (
    <LegalPage
      seo={seo}
      path="/terms"
      label="服务条款 · TERMS"
      title="服务条款"
      subtitle="以下条款适用于你对本网站的访问与使用，以及通过本网站发起的咨询。请在使用前阅读。"
      updated="2026 年 6 月"
    >
      <h2>关于本网站</h2>
      <p>
        本网站是 Five Oranges AI / 运帷AI 的信息展示与咨询入口，用于介绍我们的服务、方法与案例，并提供联系与预约方式。
      </p>

      <h2>内容仅供参考</h2>
      <p>
        网站上的内容、示例、演示与数据仅供一般性参考，用于说明我们的能力与方法，不构成对具体结果的承诺，也不构成专业咨询、法律、财务或投资建议。
      </p>

      <h2>咨询与沟通</h2>
      <p>
        你通过表单或邮件提交的咨询，仅用于双方初步沟通，不构成任何正式合同或合作关系。具体的合作范围、交付内容与商务条款，以双方另行签署的书面协议为准。
      </p>

      <h2>知识产权</h2>
      <p>
        除非另有说明，本网站的文字、设计、图形与标识均归 Five Oranges AI / 运帷AI 所有，未经许可不得用于商业用途的复制或转载。
      </p>

      <h2>第三方链接</h2>
      <p>本网站可能包含指向第三方网站的链接。我们对第三方网站的内容与隐私做法不承担责任。</p>

      <h2>责任限制</h2>
      <p>
        在适用法律允许的范围内，对于因使用本网站或依赖网站内容而产生的任何间接或后果性损失，我们不承担责任。
      </p>

      <h2>条款变更</h2>
      <p>我们可能不时更新本条款。更新后将在本页面公布最新版本与更新日期。继续使用本网站即表示你接受更新后的条款。</p>

      <h2>联系我们</h2>
      <p>
        如对本条款有任何疑问，请联系{" "}
        <a href={`mailto:${EMAIL}`}>{EMAIL}</a>。
      </p>
    </LegalPage>
  );
}
