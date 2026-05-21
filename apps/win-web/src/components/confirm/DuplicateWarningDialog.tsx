// Dialog shown before final submit when the candidate JSON warns about a
// suspected duplicate customer. The user picks "新建 / 关联已有客户".
//
// Decoupled from the network — the parent owns the candidate JSON, the
// chosen resolution map, and the actual submit call.

import type { CandidateEntity } from "../../data/candidate";

export type DuplicateMatch = {
  /** temp_id of the candidate entity flagged as a possible duplicate. */
  tempId: string;
  /**
   * Suggested existing rows the user can pick. Empty list means the
   * warning didn't carry suggestions — the user can only choose
   * "新建" or cancel and resolve in another flow.
   */
  candidates: Array<{
    id: string;
    label: string;
    hint?: string;
  }>;
};

export type DuplicateWarningDialogProps = {
  match: DuplicateMatch;
  entity: CandidateEntity;
  onResolve: (decision: "create" | string) => void;
  onCancel: () => void;
};

export function DuplicateWarningDialog(props: DuplicateWarningDialogProps) {
  const { match, entity, onResolve, onCancel } = props;
  const fullName = entity.fields.find((f) => f.name === "full_name")?.value;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,35,64,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        zIndex: 200,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480,
          maxWidth: "100%",
          background: "#fff",
          borderRadius: 14,
          padding: 24,
          boxShadow: "0 24px 64px rgba(15,35,64,0.20)",
        }}
      >
        <div
          style={{
            fontSize: 17,
            fontWeight: 700,
            color: "var(--ink-900)",
            marginBottom: 6,
          }}
        >
          疑似已有客户
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--ink-500)",
            marginBottom: 16,
            lineHeight: 1.55,
          }}
        >
          AI 在系统中找到了和"
          <strong style={{ color: "var(--ink-900)" }}>{String(fullName ?? "—")}</strong>
          "可能重复的客户。请选择：
        </div>

        {match.candidates.length > 0 ? (
          <div style={{ marginBottom: 16 }}>
            {match.candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => onResolve(c.id)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 12px",
                  marginBottom: 8,
                  border: "1px solid var(--ink-100)",
                  borderRadius: 10,
                  background: "var(--surface-2)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink-900)" }}>
                  关联到「{c.label}」
                </div>
                {c.hint ? (
                  <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
                    {c.hint}
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        ) : null}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            onClick={onCancel}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: "1px solid var(--ink-100)",
              background: "transparent",
              color: "var(--ink-700)",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            取消
          </button>
          <button
            onClick={() => onResolve("create")}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: "none",
              background: "var(--ink-900)",
              color: "#fff",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            新建一条
          </button>
        </div>
      </div>
    </div>
  );
}
