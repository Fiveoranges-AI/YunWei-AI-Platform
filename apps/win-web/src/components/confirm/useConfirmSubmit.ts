// Submit hook — bridges the display layer (ConfirmCard) with the API.
//
// Two responsibilities:
//   1. Track per-entity edits (fieldName → new value).
//   2. Build the ConfirmEntitiesRequest and call /api/win/confirm/entities.
//
// All UI state is kept here so the cards stay presentational and easy
// to reuse from a future mini-program / 企微 H5 (same logic + a
// different renderer).

import { useCallback, useState } from "react";
import { confirmEntities, type ConfirmApiError } from "../../api/confirm";
import type {
  CandidateEntity,
  CandidateJSON,
  ConfirmEntityDraft,
  ConfirmEntitiesResponse,
  ConfirmFieldDraft,
  WrittenEntity,
} from "../../data/candidate";

export type EntityEditState = Record<string, unknown>; // fieldName → new value

export type ConfirmSubmitOptions = {
  /**
   * Resolution map for entities flagged as duplicates. Keyed by temp_id;
   * value is either `"create"` (insert new row, default if absent) or an
   * existing entity UUID string ("associate with existing X"). The hook
   * does not detect duplicates itself — it only honours the user's choice.
   */
  duplicateResolutions?: Record<string, "create" | string>;
};

export type ConfirmSubmitState = {
  // Per-entity edits, keyed by temp_id.
  edits: Record<string, EntityEditState>;
  // Per-entity confirmation status (true once written successfully).
  confirmed: Record<string, boolean>;
  // Most recent write outcome by temp_id, for displaying audit chips.
  writtenByTempId: Record<string, WrittenEntity>;
  // Submit in flight (whole batch OR single-entity submit).
  busy: boolean;
  error: string | null;
};

export type UseConfirmSubmit = ConfirmSubmitState & {
  editField: (tempId: string, fieldName: string, value: unknown) => void;
  resetEditsFor: (tempId: string) => void;
  submitOne: (tempId: string, opts?: ConfirmSubmitOptions) => Promise<void>;
  submitAll: (opts?: ConfirmSubmitOptions) => Promise<void>;
};

export function useConfirmSubmit(candidate: CandidateJSON): UseConfirmSubmit {
  const [edits, setEdits] = useState<Record<string, EntityEditState>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [writtenByTempId, setWrittenByTempId] = useState<Record<string, WrittenEntity>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const editField = useCallback(
    (tempId: string, fieldName: string, value: unknown) => {
      setEdits((prev) => ({
        ...prev,
        [tempId]: { ...(prev[tempId] ?? {}), [fieldName]: value },
      }));
    },
    [],
  );

  const resetEditsFor = useCallback((tempId: string) => {
    setEdits((prev) => {
      const next = { ...prev };
      delete next[tempId];
      return next;
    });
  }, []);

  const submitBatch = useCallback(
    async (
      tempIds: string[],
      opts: ConfirmSubmitOptions | undefined,
    ): Promise<void> => {
      if (busy) return;
      // Filter out already-confirmed entities (idempotency).
      const toSubmit = tempIds.filter((tid) => !confirmed[tid]);
      if (toSubmit.length === 0) return;

      setBusy(true);
      setError(null);
      try {
        const requestEntities: ConfirmEntityDraft[] = toSubmit.map((tid) => {
          const entity = candidate.entities.find((e) => e.temp_id === tid);
          if (!entity) {
            throw new Error(`temp_id ${tid} not found in candidate`);
          }
          const editsForEntity = edits[tid] ?? {};
          const resolution = opts?.duplicateResolutions?.[tid];
          const existing =
            resolution && resolution !== "create" ? resolution : null;
          return buildEntityDraft(entity, editsForEntity, existing);
        });
        // Keep only relationships whose endpoints are in the submitted slice
        // (or already-confirmed earlier — in which case we omit them because
        // the writer expects all referenced temp_ids in the same call).
        const submittedSet = new Set(toSubmit);
        const relationships = candidate.relationships.filter(
          (r) => submittedSet.has(r.from_temp_id) && submittedSet.has(r.to_temp_id),
        );
        const response: ConfirmEntitiesResponse = await confirmEntities({
          ingestion_id: candidate.ingestion_id,
          source_type: candidate.source.type,
          source_ref: candidate.source.file_ref,
          entities: requestEntities,
          relationships,
        });
        setConfirmed((prev) => {
          const next = { ...prev };
          for (const tid of toSubmit) next[tid] = true;
          return next;
        });
        setWrittenByTempId((prev) => {
          const next = { ...prev };
          for (const w of response.written) next[w.temp_id] = w;
          return next;
        });
      } catch (e) {
        const apiErr = e as ConfirmApiError;
        setError(apiErr.message || "提交失败");
      } finally {
        setBusy(false);
      }
    },
    [busy, candidate, confirmed, edits],
  );

  const submitOne = useCallback(
    (tempId: string, opts?: ConfirmSubmitOptions) =>
      submitBatch([tempId], opts),
    [submitBatch],
  );

  const submitAll = useCallback(
    (opts?: ConfirmSubmitOptions) =>
      submitBatch(
        candidate.entities.map((e) => e.temp_id),
        opts,
      ),
    [submitBatch, candidate],
  );

  return {
    edits,
    confirmed,
    writtenByTempId,
    busy,
    error,
    editField,
    resetEditsFor,
    submitOne,
    submitAll,
  };
}

// ---- helpers -----------------------------------------------------------

function buildEntityDraft(
  entity: CandidateEntity,
  edits: EntityEditState,
  existingEntityId: string | null,
): ConfirmEntityDraft {
  const fieldByName = new Map(entity.fields.map((f) => [f.name, f]));
  const editedNames = new Set(Object.keys(edits));

  const fields: ConfirmFieldDraft[] = [];

  // Original fields first — preserving their confidence/source_span unless
  // the user edited them.
  for (const f of entity.fields) {
    const wasEdited = editedNames.has(f.name);
    fields.push({
      name: f.name,
      value: wasEdited ? edits[f.name] : f.value,
      // Per spec: human-edited fields drop their model confidence.
      confidence: wasEdited ? null : f.confidence,
      was_edited: wasEdited,
      source_span: f.source_span ?? null,
    });
  }

  // Then fields the user filled from missing_required that weren't in the
  // original candidate.
  for (const [name, value] of Object.entries(edits)) {
    if (fieldByName.has(name)) continue;
    fields.push({
      name,
      value,
      confidence: null,
      was_edited: true,
      source_span: null,
    });
  }

  return {
    entity_type: entity.entity_type,
    temp_id: entity.temp_id,
    fields,
    existing_entity_id: existingEntityId ?? null,
  };
}
