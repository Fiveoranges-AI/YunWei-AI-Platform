export type YonyouProductRow = {
  cInvCode?: string;
  cInvName?: string;
  cInvStd?: string;
  cComUnitName?: string;
  cInvCCode?: string;
};

export type ProductImportDraft = {
  targetTable: "products";
  sourceSystem: string;
  sourceRecordId: string;
  extractedData: {
    sku: string;
    name: string;
    specification?: string;
    unit?: string;
    category?: string;
  };
};

export function mapYonyouProductRow(
  row: YonyouProductRow,
  sourceSystem = "yonyou_placeholder",
): ProductImportDraft {
  const sku = row.cInvCode?.trim() || "UNKNOWN_PRODUCT";
  return {
    targetTable: "products",
    sourceSystem,
    sourceRecordId: sku,
    extractedData: {
      sku,
      name: row.cInvName?.trim() || sku,
      specification: row.cInvStd?.trim() || undefined,
      unit: row.cComUnitName?.trim() || undefined,
      category: row.cInvCCode?.trim() || undefined,
    },
  };
}
