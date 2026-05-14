// Source panel for the vNext review wizard.
//
// Shows the original document when one is uploaded (PDF/image inline,
// other types as a download link), or the raw source text for pasted /
// text-mode ingest. Below the preview we surface the cell's
// ``source_refs`` so the reviewer can see exactly which chunk / sheet
// cell / paragraph the AI cited for the currently focused cell.

import type { ReviewSourceRef } from "../../data/types";

type Props = {
  sourceText: string | null;
  originalFileUrl: string | null;
  originalFileContentType: string | null;
  activeCell?: {
    table: string;
    field: string;
    label: string;
    refs: ReviewSourceRef[];
  } | null;
};

function FilePreview({ url, contentType }: { url: string; contentType: string | null }) {
  const ct = (contentType || "").toLowerCase();
  if (ct.startsWith("image/")) {
    return (
      <img
        src={url}
        alt="原始文件"
        style={{
          width: "100%",
          maxHeight: 480,
          objectFit: "contain",
          borderRadius: 8,
          background: "var(--surface-2)",
        }}
      />
    );
  }
  if (ct.includes("pdf")) {
    return (
      <iframe
        title="原始文件"
        src={url}
        style={{
          width: "100%",
          height: 520,
          border: "1px solid var(--ink-100)",
          borderRadius: 8,
          background: "var(--surface-2)",
        }}
      />
    );
  }
  return (
    <a
      className="btn btn-secondary"
      href={url}
      target="_blank"
      rel="noreferrer"
      style={{ alignSelf: "flex-start" }}
    >
      下载原始文件
    </a>
  );
}

function SourceRefRow({ ref: r }: { ref: ReviewSourceRef }) {
  const bits: string[] = [];
  if (r.page != null) bits.push(`第 ${r.page} 页`);
  if (r.sheet) bits.push(`表 ${r.sheet}`);
  if (r.row != null) bits.push(`行 ${r.row}`);
  if (r.col != null) bits.push(`列 ${r.col}`);
  if (r.paragraph != null) bits.push(`段 ${r.paragraph}`);
  return (
    <li
      style={{
        listStyle: "none",
        padding: "8px 10px",
        background: "var(--surface-2)",
        borderRadius: 8,
        border: "1px solid var(--ink-100)",
        marginBottom: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "baseline",
          flexWrap: "wrap",
          fontSize: 12,
          color: "var(--ink-700)",
        }}
      >
        <span
          style={{
            padding: "1px 6px",
            background: "var(--brand-50)",
            color: "var(--brand-700)",
            borderRadius: 4,
            fontWeight: 600,
          }}
        >
          {r.ref_type}
        </span>
        <code style={{ color: "var(--ink-500)" }}>{r.ref_id}</code>
        {bits.length > 0 ? (
          <span style={{ color: "var(--ink-500)" }}>· {bits.join(" / ")}</span>
        ) : null}
      </div>
      {r.excerpt ? (
        <div
          style={{
            marginTop: 4,
            fontSize: 13,
            color: "var(--ink-900)",
            whiteSpace: "pre-wrap",
          }}
        >
          {r.excerpt}
        </div>
      ) : null}
    </li>
  );
}

export function ReviewSourcePanel({
  sourceText,
  originalFileUrl,
  originalFileContentType,
  activeCell,
}: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        padding: 16,
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        borderRadius: 12,
      }}
    >
      <div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--ink-700)",
            marginBottom: 8,
          }}
        >
          原始资料
        </div>
        {originalFileUrl ? (
          <FilePreview url={originalFileUrl} contentType={originalFileContentType} />
        ) : sourceText ? (
          <pre
            style={{
              margin: 0,
              padding: 12,
              background: "var(--surface-2)",
              borderRadius: 8,
              fontFamily: "var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)",
              fontSize: 13,
              color: "var(--ink-900)",
              whiteSpace: "pre-wrap",
              maxHeight: 420,
              overflow: "auto",
            }}
          >
            {sourceText}
          </pre>
        ) : (
          <div style={{ color: "var(--ink-400)", fontSize: 13 }}>
            没有可预览的原始资料。
          </div>
        )}
      </div>

      <div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--ink-700)",
            marginBottom: 8,
          }}
        >
          来源引用
        </div>
        {activeCell ? (
          <>
            <div style={{ fontSize: 12, color: "var(--ink-500)", marginBottom: 6 }}>
              {activeCell.table} · {activeCell.label}
            </div>
            {activeCell.refs.length === 0 ? (
              <div style={{ color: "var(--ink-400)", fontSize: 13 }}>
                AI 未给出此字段的来源引用。
              </div>
            ) : (
              <ul style={{ margin: 0, padding: 0 }}>
                {activeCell.refs.map((r, idx) => (
                  <SourceRefRow key={`${r.ref_id}:${idx}`} ref={r} />
                ))}
              </ul>
            )}
          </>
        ) : (
          <div style={{ color: "var(--ink-400)", fontSize: 13 }}>
            选中一个字段查看来源。
          </div>
        )}
      </div>
    </div>
  );
}
