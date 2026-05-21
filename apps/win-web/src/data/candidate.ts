// CandidateJSON shape — mirrors yunwei_win/services/parse_pipeline/candidate.py.
//
// The frontend ConfirmCard reads this verbatim from the parse pipeline
// output. Adding fields here means adding them on the backend Pydantic
// model first; this file is the consumer.

export type CandidateSourceType = "contract" | "wechat_screenshot" | "excel";

export type CandidateEntityType =
  | "Customer"
  | "Contact"
  | "Contract"
  | "Order"
  | "OrderLine"
  | "OrderItem"
  | "Product"
  | "Invoice"
  | "Payment";

export type CandidateSourceSpan = {
  page?: number | null;
  bbox?: number[] | null;
  text?: string | null;
  cell?: string | null;
  // Adapter-specific extras (sheet name, row index, etc.).
  [extra: string]: unknown;
};

export type CandidateField = {
  name: string;
  value: unknown;
  confidence: number;
  source_span: CandidateSourceSpan;
};

export type CandidateEntity = {
  entity_type: CandidateEntityType;
  temp_id: string;
  fields: CandidateField[];
  missing_required: string[];
};

export type CandidateRelationship = {
  from_temp_id: string;
  to_temp_id: string;
  type: string;
};

export type CandidateSource = {
  type: CandidateSourceType;
  file_ref: string;
  uploaded_by?: string | null;
  uploaded_at?: string | null;
};

export type CandidateJSON = {
  ingestion_id: string;
  source: CandidateSource;
  entities: CandidateEntity[];
  relationships: CandidateRelationship[];
  overall_confidence: number;
  warnings: string[];
};

// ---- Confirm-time edits and submit payload -----------------------------

export type ConfirmFieldDraft = {
  name: string;
  value: unknown;
  confidence: number | null;
  was_edited: boolean;
  source_span: CandidateSourceSpan | null;
};

export type ConfirmEntityDraft = {
  entity_type: CandidateEntityType;
  temp_id: string;
  fields: ConfirmFieldDraft[];
  /** If user picked "associate with existing X" in the duplicate dialog. */
  existing_entity_id?: string | null;
};

export type ConfirmEntitiesRequest = {
  ingestion_id: string;
  source_type: CandidateSourceType | string;
  source_ref: string;
  entities: ConfirmEntityDraft[];
  relationships: CandidateRelationship[];
};

export type WrittenEntity = {
  temp_id: string;
  entity_type: string;
  entity_id: string;
  created: boolean;
  human_verified: boolean;
  verified_by: string;
  field_count: number;
  edited_field_count: number;
};

export type ConfirmEntitiesResponse = {
  written: WrittenEntity[];
  action_log_ids: string[];
};
