/* =============================================================
   Data Security & AI Boundaries — /data-security
   数据安全与AI使用边界. The six required principles, grouped and
   framed as commitments/principles (not overclaimed certifications).
   ============================================================= */

import { ClipboardCheck, EyeOff, Lock, Scale, Server, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import LegalPage from "@/components/LegalPage";

const seo = {
  title: "数据安全与AI使用边界 · Data Security | Five Oranges AI / 运帷AI",
  description:
    "Five Oranges AI / 运帷AI 的数据安全与 AI 使用边界：客户数据不用于训练公共模型、仅在授权范围内使用、支持脱敏、权限控制与可审计流程，AI 输出辅助而非替代业务判断。",
  keywords:
    "数据安全, AI使用边界, 数据保护, 权限控制, 脱敏, 合规云, 制造业AI数字化, Five Oranges AI, 运帷AI",
};

type Point = { Icon: LucideIcon; statement: string; detail: string };

const DATA_POINTS: Point[] = [
  {
    Icon: ShieldCheck,
    statement: "客户数据不会用于训练公共模型。",
    detail: "你的业务数据只服务于你自己的项目，不会被用于训练面向公众的通用模型。",
  },
  {
    Icon: Lock,
    statement: "客户数据仅用于授权范围内的业务分析、系统配置和演示验证。",
    detail: "我们只在你明确授权的用途和范围内使用数据，不作他用。",
  },
  {
    Icon: EyeOff,
    statement: "敏感数据可脱敏后再进入 AI 分析流程。",
    detail: "对于敏感字段，可在进入分析前进行脱敏或最小化处理，降低暴露风险。",
  },
];

const GOVERNANCE_POINTS: Point[] = [
  {
    Icon: ClipboardCheck,
    statement: "系统应支持权限控制、访问记录和可审计的数据处理流程。",
    detail: "正式系统按角色控制访问，并保留可追溯的操作记录，便于审计。",
  },
  {
    Icon: Server,
    statement: "正式项目中可根据企业要求部署在客户指定环境或合规云环境。",
    detail: "部署位置可按你的安全与合规要求确定，包括你指定的环境或合规云。",
  },
];

const AI_POINTS: Point[] = [
  {
    Icon: Scale,
    statement: "AI 输出需要结合业务判断，不作为唯一决策依据。",
    detail: "AI 用于辅助分析与提升效率，最终决策仍由你的团队结合实际业务把关。",
  },
];

function PointList({ points }: { points: Point[] }) {
  return (
    <ul className="legal-points">
      {points.map(({ Icon, statement, detail }) => (
        <li key={statement}>
          <Icon size={20} strokeWidth={2} aria-hidden />
          <span>
            <strong>{statement}</strong>
            <br />
            {detail}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function DataSecurity() {
  return (
    <LegalPage
      seo={seo}
      path="/data-security"
      label="数据安全 · DATA SECURITY"
      title="数据安全与 AI 使用边界"
      subtitle="数据安全是企业采用 AI 的前提。以下是我们在数据使用、安全治理与 AI 边界上的基本原则；正式项目会根据你的具体要求进一步细化。"
      updated="2026 年 6 月"
    >
      <h2>数据使用边界</h2>
      <PointList points={DATA_POINTS} />

      <h2>安全、权限与部署</h2>
      <PointList points={GOVERNANCE_POINTS} />

      <h2>AI 使用边界</h2>
      <PointList points={AI_POINTS} />

      <h2>说明</h2>
      <p>
        以上为通用性原则，用于说明我们对待企业数据与 AI
        的基本态度，不构成对特定法律法规合规性的承诺。具体的数据处理、权限与部署方案，会在正式项目中根据你的行业要求与内部规范共同确定，并以双方签署的协议为准。如需进一步沟通，欢迎{" "}
        <a href="/strategy-call">预约一次低风险的战略沟通</a>。
      </p>
    </LegalPage>
  );
}
