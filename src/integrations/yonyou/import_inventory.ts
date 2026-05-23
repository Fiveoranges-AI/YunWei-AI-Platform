export type YonyouInventoryRow = {
  cWhCode?: string;
  cInvCode?: string;
  iQuantity?: string | number;
  dVDate?: string;
  cBatch?: string;
};

export type InventoryImportDraft = {
  targetTable: "ai_extraction_queue";
  sourceSystem: string;
  sourceRecordId: string;
  extractedData: {
    warehouse_code?: string;
    product_source_record_id?: string;
    quantity?: number;
    snapshot_date?: string;
    batch_no?: string;
  };
};

function numberOrUndefined(value: string | number | undefined): number | undefined {
  if (value === undefined || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function mapYonyouInventoryRow(
  row: YonyouInventoryRow,
  sourceSystem = "yonyou_placeholder",
): InventoryImportDraft {
  const productCode = row.cInvCode?.trim() || "UNKNOWN_PRODUCT";
  const warehouseCode = row.cWhCode?.trim() || "UNKNOWN_WAREHOUSE";
  return {
    targetTable: "ai_extraction_queue",
    sourceSystem,
    sourceRecordId: `${warehouseCode}:${productCode}:${row.cBatch || "NO_BATCH"}`,
    extractedData: {
      warehouse_code: warehouseCode,
      product_source_record_id: productCode,
      quantity: numberOrUndefined(row.iQuantity),
      snapshot_date: row.dVDate?.trim() || undefined,
      batch_no: row.cBatch?.trim() || undefined,
    },
  };
}
