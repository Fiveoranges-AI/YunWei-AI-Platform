import { useEffect, useState, type ReactNode } from "react";
import type { GoFn } from "../App";
import {
  deleteCustomer,
  getCustomer,
  replaceCustomerContacts,
  updateCustomer,
  type ContactInput,
} from "../api/client";
import { AISummary } from "../components/AISummary";
import { EvidenceChip } from "../components/EvidenceChip";
import { Mono } from "../components/Mono";
import { RowCard } from "../components/RowCard";
import { Section } from "../components/Section";
import { SmallStat } from "../components/SmallStat";
import type { Contact, CustomerDetail, TimelineEvent } from "../data/types";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";
import { fmtCNYRaw } from "../lib/format";

type EditableContact = {
  key: string;
  id?: string;
  name: string;
  title: string;
  phone: string;
  mobile: string;
  email: string;
  role: string;
  address: string;
  wechatId: string;
};

const CONTACT_ROLES: { value: string; label: string }[] = [
  { value: "buyer", label: "采购" },
  { value: "delivery", label: "收货" },
  { value: "acceptance", label: "验收" },
  { value: "invoice", label: "开票" },
  { value: "seller", label: "销售" },
  { value: "other", label: "其他" },
];

function genKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `tmp-${crypto.randomUUID()}`;
  }
  return `tmp-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

function contactsToEditable(contacts: Contact[] | undefined): EditableContact[] {
  if (!contacts) return [];
  return contacts.map((c) => ({
    key: c.id,
    id: c.id,
    name: c.name ?? "",
    title: c.title ?? "",
    phone: c.phone ?? "",
    mobile: c.mobile ?? "",
    email: c.email ?? "",
    role: c.role || "other",
    address: c.address ?? "",
    wechatId: c.wechatId ?? "",
  }));
}

const INPUT_STYLE: React.CSSProperties = {
  width: "100%",
  border: "1px solid var(--ink-100)",
  borderRadius: 10,
  padding: "9px 12px",
  fontFamily: "var(--font)",
  fontSize: 14,
  color: "var(--ink-800)",
  background: "var(--surface)",
  outline: "none",
  boxSizing: "border-box",
};

const LABEL_STYLE: React.CSSProperties = {
  fontSize: 12,
  color: "var(--ink-500)",
  fontWeight: 600,
  marginBottom: 4,
  display: "block",
};

const TIMELINE_ICON: Record<TimelineEvent["kind"], (s?: number) => ReactNode> = {
  upload: (s = 13) => I.cloud(s),
  meet: (s = 13) => I.voice(s),
  wechat: (s = 13) => I.wechat(s),
  invoice: (s = 13) => I.cash(s),
};

export function CustomerDetailScreen({
  go,
  params,
}: {
  go: GoFn;
  params: Record<string, string>;
}) {
  const isDesktop = useIsDesktop();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (params.id) {
      setLoadError(null);
      setEditing(false);
      getCustomer(params.id)
        .then((c) => setCustomer(c ?? null))
        .catch((e) => {
          setCustomer(null);
          setLoadError(e instanceof Error ? e.message : "客户档案加载失败");
        });
    }
  }, [params.id]);

  if (loadError) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ textAlign: "center", padding: 24 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            客户档案加载失败
          </div>
          <div style={{ color: "var(--ink-500)", fontSize: 13, marginBottom: 16 }}>{loadError}</div>
          <button className="btn btn-secondary" onClick={() => go("list")}>
            返回客户列表
          </button>
        </div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div
        className="screen"
        style={{ background: "var(--bg)", alignItems: "center", justifyContent: "center", display: "flex" }}
      >
        <div style={{ color: "var(--ink-400)", fontSize: 14 }}>加载中…</div>
      </div>
    );
  }

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {/* Top nav */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isDesktop ? "12px 32px 8px" : "6px 8px 8px",
          maxWidth: isDesktop ? 1280 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <button
          onClick={() => go("list")}
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: "transparent",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-700)",
            cursor: "pointer",
          }}
        >
          {I.back(22)}
        </button>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink-700)" }}>客户档案</div>
        <button
          onClick={() => setEditing((v) => !v)}
          style={{
            height: 32,
            padding: "0 14px",
            borderRadius: 16,
            background: editing ? "var(--ink-100)" : "transparent",
            border: "1px solid var(--ink-100)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {editing ? "完成" : "编辑"}
        </button>
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "0 32px 40px" : "0 16px 120px",
          maxWidth: isDesktop ? 1280 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {isDesktop ? (
          <DesktopLayout
            customer={customer}
            go={go}
            editing={editing}
            setEditing={setEditing}
            setCustomer={setCustomer}
          />
        ) : (
          <MobileLayout
            customer={customer}
            go={go}
            editing={editing}
            setEditing={setEditing}
            setCustomer={setCustomer}
          />
        )}
      </div>
    </div>
  );
}

type LayoutProps = {
  customer: CustomerDetail;
  go: GoFn;
  editing: boolean;
  setEditing: (v: boolean) => void;
  setCustomer: (c: CustomerDetail) => void;
};

function MobileLayout({ customer, go, editing, setEditing, setCustomer }: LayoutProps) {
  return (
    <>
      <Header customer={customer} />
      {editing && (
        <EditPanel
          customer={customer}
          onCancel={() => setEditing(false)}
          onSaved={(c) => {
            setCustomer(c);
            setEditing(false);
          }}
          onDeleted={() => go("list")}
        />
      )}
      <AISummary style={{ marginBottom: 12 }}>{customer.aiSummary}</AISummary>
      <KeyMetricsRow customer={customer} />
      <SmallMetricsRow customer={customer} />
      <AskCustomerCTA customer={customer} go={go} />
      <RisksSection customer={customer} />
      <CommitmentsSection customer={customer} />
      <TasksSection customer={customer} />
      <TimelineSection customer={customer} />
      <ContactsSection customer={customer} />
      <DocsSection customer={customer} />
    </>
  );
}

function DesktopLayout({ customer, go, editing, setEditing, setCustomer }: LayoutProps) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 24, alignItems: "flex-start" }}>
      {/* Main column */}
      <div>
        <Header customer={customer} />
        {editing && (
          <EditPanel
            customer={customer}
            onCancel={() => setEditing(false)}
            onSaved={(c) => {
              setCustomer(c);
              setEditing(false);
            }}
            onDeleted={() => go("list")}
          />
        )}
        <AISummary style={{ marginBottom: 16 }}>{customer.aiSummary}</AISummary>
        <RisksSection customer={customer} />
        <CommitmentsSection customer={customer} />
        <TasksSection customer={customer} />
        <TimelineSection customer={customer} />
        <DocsSection customer={customer} />
      </div>

      {/* Sticky right rail */}
      <aside style={{ position: "sticky", top: 12, display: "flex", flexDirection: "column", gap: 12 }}>
        <KeyMetricsRow customer={customer} />
        <SmallMetricsRow customer={customer} />
        <AskCustomerCTA customer={customer} go={go} />
        <ContactsSection customer={customer} />
      </aside>
    </div>
  );
}

function EditPanel({
  customer,
  onCancel,
  onSaved,
  onDeleted,
}: {
  customer: CustomerDetail;
  onCancel: () => void;
  onSaved: (next: CustomerDetail) => void;
  onDeleted: () => void;
}) {
  const [fullName, setFullName] = useState(customer.name);
  const [shortName, setShortName] = useState(customer.shortName ?? "");
  const [address, setAddress] = useState(customer.address ?? "");
  const [taxId, setTaxId] = useState(customer.taxId ?? "");
  const [formContacts, setFormContacts] = useState<EditableContact[]>(() => contactsToEditable(customer.contacts));
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  function updateContact(key: string, patch: Partial<EditableContact>) {
    setFormContacts((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function removeContact(key: string) {
    setFormContacts((rows) => rows.filter((r) => r.key !== key));
  }

  function addContact() {
    setFormContacts((rows) => [
      ...rows,
      {
        key: genKey(),
        name: "",
        title: "",
        phone: "",
        mobile: "",
        email: "",
        role: "other",
        address: "",
        wechatId: "",
      },
    ]);
  }

  async function save() {
    if (!fullName.trim()) {
      setActionError("客户全称不能为空");
      return;
    }
    if (formContacts.some((c) => !c.name.trim())) {
      setActionError("联系人姓名不能为空");
      return;
    }
    setSaving(true);
    setActionError(null);
    try {
      await updateCustomer(customer.id, {
        full_name: fullName.trim(),
        short_name: shortName.trim() || null,
        address: address.trim() || null,
        tax_id: taxId.trim() || null,
      });
      const payload: ContactInput[] = formContacts.map((c) => {
        const base: ContactInput = {
          name: c.name.trim(),
          title: c.title.trim() || null,
          phone: c.phone.trim() || null,
          mobile: c.mobile.trim() || null,
          email: c.email.trim() || null,
          role: c.role || "other",
          address: c.address.trim() || null,
          wechat_id: c.wechatId.trim() || null,
        };
        // Existing contacts have a real backend id (not tmp-...); send it back.
        if (c.id && !c.id.startsWith("tmp-")) {
          base.id = c.id;
        }
        return base;
      });
      await replaceCustomerContacts(customer.id, payload);
      const fresh = await getCustomer(customer.id);
      if (fresh) onSaved(fresh);
      else onSaved(customer);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (
      !window.confirm(
        `确定要删除客户「${customer.name}」吗？此操作不可撤销，将同时删除该客户的合同、订单、联系人、记忆与任务记录。`,
      )
    ) {
      return;
    }
    setDeleting(true);
    setActionError(null);
    try {
      await deleteCustomer(customer.id);
      onDeleted();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "删除失败");
      setDeleting(false);
    }
  }

  const busy = saving || deleting;

  return (
    <div
      className="card"
      style={{
        padding: 16,
        marginBottom: 16,
        border: "1px solid var(--ink-100)",
        background: "var(--surface)",
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", marginBottom: 12 }}>
        编辑客户信息
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div style={{ gridColumn: "1 / -1" }}>
          <label style={LABEL_STYLE}>客户全称 *</label>
          <input
            style={INPUT_STYLE}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="客户全称"
            disabled={busy}
          />
        </div>
        <div>
          <label style={LABEL_STYLE}>简称</label>
          <input
            style={INPUT_STYLE}
            value={shortName}
            onChange={(e) => setShortName(e.target.value)}
            placeholder="简称"
            disabled={busy}
          />
        </div>
        <div>
          <label style={LABEL_STYLE}>税号</label>
          <input
            style={INPUT_STYLE}
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
            placeholder="税号"
            disabled={busy}
          />
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label style={LABEL_STYLE}>地址</label>
          <input
            style={INPUT_STYLE}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="地址"
            disabled={busy}
          />
        </div>
      </div>

      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "var(--ink-900)",
          marginTop: 4,
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span>联系人 · {formContacts.length}</span>
        <button
          type="button"
          onClick={addContact}
          disabled={busy}
          style={{
            height: 28,
            padding: "0 10px",
            borderRadius: 14,
            border: "1px solid var(--ink-100)",
            background: "var(--surface)",
            color: "var(--ink-700)",
            cursor: busy ? "not-allowed" : "pointer",
            fontFamily: "var(--font)",
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          + 添加联系人
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
        {formContacts.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--ink-400)", padding: "8px 0" }}>
            暂无联系人。点击「添加联系人」新增。
          </div>
        )}
        {formContacts.map((c) => (
          <div
            key={c.key}
            style={{
              border: "1px solid var(--ink-100)",
              borderRadius: 12,
              padding: 10,
              background: "var(--bg)",
            }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label style={LABEL_STYLE}>姓名 *</label>
                <input
                  style={INPUT_STYLE}
                  value={c.name}
                  onChange={(e) => updateContact(c.key, { name: e.target.value })}
                  placeholder="姓名"
                  disabled={busy}
                />
              </div>
              <div>
                <label style={LABEL_STYLE}>职位</label>
                <input
                  style={INPUT_STYLE}
                  value={c.title}
                  onChange={(e) => updateContact(c.key, { title: e.target.value })}
                  placeholder="职位"
                  disabled={busy}
                />
              </div>
              <div>
                <label style={LABEL_STYLE}>手机</label>
                <input
                  style={INPUT_STYLE}
                  value={c.mobile}
                  onChange={(e) => updateContact(c.key, { mobile: e.target.value })}
                  placeholder="手机"
                  disabled={busy}
                />
              </div>
              <div>
                <label style={LABEL_STYLE}>邮箱</label>
                <input
                  style={INPUT_STYLE}
                  value={c.email}
                  onChange={(e) => updateContact(c.key, { email: e.target.value })}
                  placeholder="邮箱"
                  disabled={busy}
                />
              </div>
              <div>
                <label style={LABEL_STYLE}>角色</label>
                <select
                  style={INPUT_STYLE}
                  value={c.role}
                  onChange={(e) => updateContact(c.key, { role: e.target.value })}
                  disabled={busy}
                >
                  {CONTACT_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => removeContact(c.key)}
                  disabled={busy}
                  style={{
                    height: 32,
                    padding: "0 10px",
                    borderRadius: 8,
                    border: "1px solid var(--ink-100)",
                    background: "transparent",
                    color: "var(--risk-700)",
                    cursor: busy ? "not-allowed" : "pointer",
                    fontFamily: "var(--font)",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  删除联系人
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {actionError && (
        <div
          style={{
            fontSize: 13,
            color: "var(--risk-700)",
            background: "var(--risk-100)",
            border: "1px solid #f4cfcf",
            padding: "8px 12px",
            borderRadius: 10,
            marginBottom: 10,
          }}
        >
          {actionError}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          style={{
            height: 36,
            padding: "0 16px",
            borderRadius: 18,
            border: "1px solid var(--ink-100)",
            background: "var(--surface)",
            color: "var(--ink-700)",
            cursor: busy ? "not-allowed" : "pointer",
            fontFamily: "var(--font)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          取消
        </button>
        <button
          type="button"
          onClick={save}
          disabled={busy}
          style={{
            height: 36,
            padding: "0 16px",
            borderRadius: 18,
            border: "none",
            background: "var(--ink-900)",
            color: "#fff",
            cursor: busy ? "not-allowed" : "pointer",
            fontFamily: "var(--font)",
            fontSize: 13,
            fontWeight: 600,
            opacity: busy ? 0.6 : 1,
          }}
        >
          {saving ? "保存中…" : "保存"}
        </button>
      </div>

      <div
        style={{
          marginTop: 12,
          paddingTop: 12,
          borderTop: "1px dashed var(--ink-100)",
          display: "flex",
          justifyContent: "flex-end",
        }}
      >
        <button
          type="button"
          onClick={handleDelete}
          disabled={busy}
          style={{
            height: 32,
            padding: "0 12px",
            borderRadius: 16,
            border: "1px solid #f4cfcf",
            background: "var(--risk-100)",
            color: "var(--risk-700)",
            cursor: busy ? "not-allowed" : "pointer",
            fontFamily: "var(--font)",
            fontSize: 12,
            fontWeight: 600,
            opacity: busy ? 0.6 : 1,
          }}
        >
          {deleting ? "删除中…" : "删除客户"}
        </button>
      </div>
    </div>
  );
}

function Header({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "flex", gap: 14, alignItems: "flex-start", marginBottom: 12 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 24,
            fontWeight: 700,
            color: "var(--ink-900)",
            letterSpacing: "-0.01em",
            lineHeight: 1.2,
          }}
        >
          {customer.name}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          <span className="pill pill-brand" style={{ fontSize: 11 }}>
            {customer.tag}
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-500)" }}>· 最近更新 {customer.updated}</span>
        </div>
      </div>
    </div>
  );
}

function KeyMetricsRow({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
      <div className="card" style={{ padding: 12 }}>
        <div style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600, letterSpacing: "0.02em" }}>
          合同总额
        </div>
        <div className="num" style={{ fontSize: 19, fontWeight: 700, color: "var(--ink-900)", marginTop: 4 }}>
          {fmtCNYRaw(customer.metrics.contractTotal)}
        </div>
      </div>
      <div
        className="card"
        style={{ padding: 12, background: "var(--warn-100)", border: "1px solid #f4dfb6" }}
      >
        <div style={{ fontSize: 11, color: "var(--warn-700)", fontWeight: 600, letterSpacing: "0.02em" }}>
          未收款
        </div>
        <div className="num" style={{ fontSize: 19, fontWeight: 700, color: "var(--warn-700)", marginTop: 4 }}>
          {fmtCNYRaw(customer.metrics.receivable)}
        </div>
      </div>
    </div>
  );
}

function SmallMetricsRow({ customer }: { customer: CustomerDetail }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
      <SmallStat icon={I.doc(15)} label="合同" value={customer.metrics.contracts} />
      <SmallStat icon={I.task(15)} label="待办" value={customer.metrics.tasks} tone="ai" />
      <SmallStat icon={I.customers(15)} label="联系人" value={customer.metrics.contacts} />
    </div>
  );
}

function AskCustomerCTA({ customer, go }: { customer: CustomerDetail; go: GoFn }) {
  return (
    <button
      onClick={() => go("ask", { id: customer.id })}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 14px",
        borderRadius: 14,
        marginBottom: 16,
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        boxShadow: "var(--shadow-card-soft)",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 16,
          background: "var(--ai-100)",
          color: "var(--ai-500)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {I.spark(14)}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>问问这个客户</div>
        <div style={{ fontSize: 12, color: "var(--ink-500)" }}>例：还有多少钱没收？最近沟通说了什么？</div>
      </div>
      <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
    </button>
  );
}

function RisksSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.risks?.length) return null;
  return (
    <Section title="风险线索">
      {customer.risks.map((r) => (
        <div
          key={r.id}
          style={{
            background: "var(--surface)",
            borderRadius: 14,
            border: "1px solid var(--ink-100)",
            borderLeft: "3px solid var(--warn-500)",
            padding: 12,
            marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--warn-500)" }}>{I.warn(15)}</span>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{r.title}</div>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-700)", marginTop: 6, lineHeight: 1.5 }}>{r.detail}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {r.sources.map((s, i) => (
              <EvidenceChip key={i} type={s.startsWith("微信") ? "微信" : "文件"} label={s} />
            ))}
          </div>
        </div>
      ))}
    </Section>
  );
}

function CommitmentsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.commitments?.length) return null;
  return (
    <Section title="承诺事项" count={customer.commitments.length}>
      {customer.commitments.map((x) => (
        <RowCard key={x.id} icon={I.hand(16)} iconBg="var(--warn-100)" iconColor="var(--warn-700)">
          <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{x.text}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            <EvidenceChip type={x.source.includes("微信") ? "微信" : "文件"} label={x.source} />
          </div>
        </RowCard>
      ))}
    </Section>
  );
}

function TasksSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.tasks?.length) return null;
  return (
    <Section title="待办事项" count={customer.tasks.length}>
      {customer.tasks.map((t) => (
        <RowCard key={t.id} icon={I.task(16)} iconBg="var(--ai-100)" iconColor="var(--ai-500)">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{t.text}</div>
            <span className="pill pill-ai" style={{ fontSize: 11, flexShrink: 0 }}>
              {t.due}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 4 }}>负责人 · {t.owner}</div>
        </RowCard>
      ))}
    </Section>
  );
}

function TimelineSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.timeline?.length) return null;
  return (
    <Section title="最近动态" trailing={<span className="more">查看全部</span>}>
      <div
        style={{
          background: "var(--surface)",
          borderRadius: 14,
          padding: "14px 16px 8px",
          border: "1px solid var(--ink-100)",
        }}
      >
        {customer.timeline.map((e, i) => {
          const last = i === customer.timeline!.length - 1;
          return (
            <div key={i} style={{ display: "flex", gap: 12, paddingBottom: last ? 6 : 14 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 11,
                    background: "var(--brand-50)",
                    color: "var(--brand-500)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {TIMELINE_ICON[e.kind]?.(13) ?? I.doc(13)}
                </div>
                {!last && <div style={{ width: 1.5, flex: 1, background: "var(--ink-100)", marginTop: 4 }} />}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, color: "var(--ink-900)", fontWeight: 500 }}>{e.title}</div>
                <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 3 }}>
                  {e.when} · {e.by}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-400)",
                    marginTop: 3,
                    fontFamily: "ui-monospace, SFMono-Regular, monospace",
                  }}
                >
                  {e.src}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function ContactsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.contacts?.length) return null;
  return (
    <Section title="联系人" count={customer.contacts.length} trailing={<span className="more">+ 添加</span>}>
      <div className="card" style={{ padding: "4px 0" }}>
        {customer.contacts.map((p, i) => (
          <div key={p.id}>
            {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 60 }} />}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
              <Mono text={p.initial} color="#7a8aa3" size={36} radius={18} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{p.name}</span>
                  <span style={{ fontSize: 11, color: "var(--ink-500)" }}>{p.role}</span>
                </div>
                <div className="num" style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>
                  {p.phone} · 最近 {p.last}
                </div>
              </div>
              <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function DocsSection({ customer }: { customer: CustomerDetail }) {
  if (!customer.docs?.length) return null;
  return (
    <Section title="来源依据" count={customer.docs.length}>
      <div className="card" style={{ padding: "4px 0" }}>
        {customer.docs.map((d, i) => (
          <div key={d.id}>
            {i > 0 && <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 60 }} />}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px" }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: "var(--surface-3)",
                  color: "var(--ink-600)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {I.doc(16)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: "var(--ink-900)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {d.name}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 2 }}>
                  {d.kind} · {d.date}
                </div>
              </div>
              <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
