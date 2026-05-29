// Demo page for P0 task ③ confirm cards.
//
// Mounts a hard-coded sample CandidateJSON (resembling task ② parse
// output) so the full confirm-card → writeback loop can be exercised
// without standing up a real parse run. The page itself is the integration
// surface: production usage will instead hand a real CandidateJSON (from
// /api/win/ingest/.../parse) into <ConfirmCardList>.

import { useMemo, useState } from "react";
import type { GoFn } from "../App";
import { ConfirmCard } from "../components/confirm/ConfirmCard";
import { DuplicateWarningDialog } from "../components/confirm/DuplicateWarningDialog";
import { useConfirmSubmit } from "../components/confirm/useConfirmSubmit";
import type { CandidateJSON } from "../data/candidate";

const SAMPLE_CANDIDATE: CandidateJSON = {
  ingestion_id: "demo-ing-2026-05-21",
  source: {
    type: "contract",
    file_ref: "storage://demo/contract-001.pdf",
    uploaded_by: "demo-user",
    uploaded_at: "2026-05-21T10:00:00+08:00",
  },
  overall_confidence: 0.78,
  warnings: ["customer_name 与既有客户「上海耀华化工有限公司」相似度 0.84,疑似重复"],
  entities: [
    {
      entity_type: "Customer",
      temp_id: "cust-1",
      missing_required: [],
      fields: [
        {
          name: "full_name",
          value: "上海耀华化工有限公司",
          confidence: 0.95,
          source_span: {
            page: 1,
            text: "甲方：上海耀华化工有限公司（以下简称甲方）",
          },
        },
        {
          name: "short_name",
          value: "耀华化工",
          confidence: 0.68,
          source_span: { page: 1, text: "简称：耀华化工" },
        },
        {
          name: "tax_id",
          value: "91310000XXXXXXX01",
          confidence: 0.91,
          source_span: { page: 1, text: "纳税人识别号: 91310000XXXXXXX01" },
        },
        {
          name: "address",
          value: "上海市浦东新区张江高科技园区祖冲之路 1199 号",
          confidence: 0.55, // 低 — 应高亮
          source_span: { page: 1, text: "地址：上海市浦东新区张江...路 1199 号" },
        },
      ],
    },
    {
      entity_type: "Contact",
      temp_id: "ct-1",
      missing_required: ["email"],
      fields: [
        {
          name: "name",
          value: "王志强",
          confidence: 0.92,
          source_span: { page: 1, text: "联系人：王志强" },
        },
        {
          name: "title",
          value: "采购经理",
          confidence: 0.7,
          source_span: { page: 1, text: "采购经理 王志强" },
        },
        {
          name: "mobile",
          value: "13800001234",
          confidence: 0.88,
          source_span: { page: 1, text: "手机:13800001234" },
        },
      ],
    },
    {
      entity_type: "Order",
      temp_id: "ord-1",
      missing_required: [],
      fields: [
        {
          name: "amount_total",
          value: 580000.0,
          confidence: 0.86,
          source_span: { page: 2, text: "合同总金额: ¥ 580,000.00 元" },
        },
        {
          name: "amount_currency",
          value: "CNY",
          confidence: 0.95,
          source_span: { page: 2, text: "币种 RMB" },
        },
        {
          name: "delivery_promised_date",
          value: "2026-06-30",
          confidence: 0.4, // 低 — 应高亮
          source_span: { page: 3, text: "交付日期：6月30日前" },
        },
      ],
    },
  ],
  relationships: [
    { from_temp_id: "cust-1", to_temp_id: "ct-1", type: "Customer-has-Contact" },
    { from_temp_id: "cust-1", to_temp_id: "ord-1", type: "Customer-has-Order" },
  ],
};

export function ConfirmDemoScreen({ go }: { go: GoFn }) {
  const candidate = SAMPLE_CANDIDATE;
  const submit = useConfirmSubmit(candidate);
  const [duplicatePromptTempId, setDuplicatePromptTempId] = useState<string | null>(null);
  const [pendingResolutions, setPendingResolutions] =
    useState<Record<string, "create" | string>>({});

  const hasDuplicateWarning = useMemo(
    () => candidate.warnings.some((w) => w.includes("重复")),
    [candidate.warnings],
  );

  const customerEntity = candidate.entities.find((e) => e.entity_type === "Customer");
  const customerTempId = customerEntity?.temp_id ?? null;

  function handleSubmitAll() {
    if (hasDuplicateWarning && customerTempId && !pendingResolutions[customerTempId]) {
      setDuplicatePromptTempId(customerTempId);
      return;
    }
    void submit.submitAll({ duplicateResolutions: pendingResolutions });
  }

  function handleResolveDuplicate(decision: "create" | string) {
    if (!duplicatePromptTempId) return;
    const next = { ...pendingResolutions, [duplicatePromptTempId]: decision };
    setPendingResolutions(next);
    setDuplicatePromptTempId(null);
    void submit.submitAll({ duplicateResolutions: next });
  }

  const allConfirmed =
    candidate.entities.length > 0 &&
    candidate.entities.every((e) => submit.confirmed[e.temp_id]);

  return (
    <div
      className="screen"
      style={{
        background: "var(--surface-2)",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ maxWidth: 880, margin: "0 auto", width: "100%", padding: "32px 24px 64px" }}>
        <Header onBack={() => go("upload")} candidateId={candidate.ingestion_id} />

        {candidate.warnings.length > 0 ? <WarningStrip warnings={candidate.warnings} /> : null}

        {candidate.entities.map((e) => (
          <ConfirmCard
            key={e.temp_id}
            entity={e}
            edits={submit.edits[e.temp_id] ?? {}}
            confirmed={Boolean(submit.confirmed[e.temp_id])}
            busy={submit.busy}
            onEditField={({ fieldName, value }) =>
              submit.editField(e.temp_id, fieldName, value)
            }
            onConfirm={() =>
              submit.submitOne(e.temp_id, { duplicateResolutions: pendingResolutions })
            }
          />
        ))}

        {submit.error ? (
          <div
            style={{
              padding: "12px 14px",
              borderRadius: 10,
              border: "1px solid var(--risk-100, #FEE2E2)",
              background: "#fff1f0",
              color: "var(--risk-700, #B91C1C)",
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            {submit.error}
          </div>
        ) : null}

        {allConfirmed ? <AuditPanel writtenByTempId={submit.writtenByTempId} /> : null}

        <button
          onClick={handleSubmitAll}
          disabled={submit.busy || allConfirmed}
          style={{
            width: "100%",
            height: 48,
            marginTop: 8,
            borderRadius: 12,
            border: "none",
            background: allConfirmed ? "var(--ok-700, #047857)" : "var(--ink-900)",
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            cursor: submit.busy || allConfirmed ? "not-allowed" : "pointer",
            opacity: submit.busy ? 0.6 : 1,
            fontFamily: "var(--font)",
          }}
          data-testid="submit-all"
        >
          {allConfirmed
            ? "全部已入库 · 人工已确认"
            : submit.busy
              ? "提交中…"
              : "全部确认并入库"}
        </button>
      </div>

      {duplicatePromptTempId && customerEntity ? (
        <DuplicateWarningDialog
          match={{
            tempId: duplicatePromptTempId,
            candidates: [
              {
                id: "00000000-0000-0000-0000-000000000001",
                label: "上海耀华化工有限公司(既有)",
                hint: "id 00000000…0001 · 上次更新 2026-04-12",
              },
            ],
          }}
          entity={customerEntity}
          onResolve={handleResolveDuplicate}
          onCancel={() => setDuplicatePromptTempId(null)}
        />
      ) : null}
    </div>
  );
}

function Header({ onBack, candidateId }: { onBack: () => void; candidateId: string }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <button
        onClick={onBack}
        style={{
          background: "transparent",
          border: "none",
          color: "var(--ink-500)",
          fontSize: 12.5,
          fontWeight: 500,
          cursor: "pointer",
          padding: 0,
          marginBottom: 12,
          fontFamily: "var(--font)",
        }}
      >
        ← 返回上传
      </button>
      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          color: "var(--ink-900)",
          letterSpacing: "-0.02em",
          marginBottom: 4,
        }}
      >
        人机确认 · 候选信息
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-500)" }}>
        AI 已解析以下条目,请核对并确认。{" "}
        <code style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11.5 }}>
          ingestion={candidateId}
        </code>
      </div>
    </div>
  );
}

function WarningStrip({ warnings }: { warnings: string[] }) {
  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: 10,
        background: "var(--warn-100, #FEF3C7)",
        color: "var(--warn-700, #B45309)",
        fontSize: 12.5,
        marginBottom: 16,
        lineHeight: 1.55,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>解析警告</div>
      {warnings.map((w, i) => (
        <div key={i}>• {w}</div>
      ))}
    </div>
  );
}

function AuditPanel({
  writtenByTempId,
}: {
  writtenByTempId: Record<string, import("../data/candidate").WrittenEntity>;
}) {
  const entries = Object.values(writtenByTempId);
  if (entries.length === 0) return null;
  return (
    <div
      style={{
        padding: "14px 16px",
        borderRadius: 10,
        background: "var(--ok-100, #D1FAE5)",
        color: "var(--ok-700, #047857)",
        marginBottom: 16,
        fontSize: 12.5,
        lineHeight: 1.55,
      }}
      data-testid="audit-panel"
    >
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13 }}>已写入 · 审计</div>
      {entries.map((w) => (
        <div key={w.temp_id} style={{ display: "flex", justifyContent: "space-between" }}>
          <span>
            {w.entity_type} · {w.created ? "新建" : "关联既有"} · 人工已确认 by{" "}
            <strong>{w.verified_by}</strong>
            {w.edited_field_count > 0
              ? ` · 修改 ${w.edited_field_count} 项`
              : ""}
          </span>
          <code
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 10.5,
              color: "var(--ok-700, #047857)",
            }}
          >
            {w.entity_id.slice(0, 8)}…
          </code>
        </div>
      ))}
    </div>
  );
}
