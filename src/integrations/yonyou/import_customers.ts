export type YonyouCustomerRow = {
  cCusCode?: string;
  cCusName?: string;
  cCusAbbName?: string;
  cCusAddress?: string;
  cCusPhone?: string;
  cCusDefine1?: string;
};

export type CustomerImportDraft = {
  targetTable: "customers";
  sourceSystem: string;
  sourceRecordId: string;
  extractedData: {
    customer_code: string;
    full_name: string;
    short_name?: string;
    address?: string;
    phone?: string;
    credit_level?: string;
  };
};

export function mapYonyouCustomerRow(
  row: YonyouCustomerRow,
  sourceSystem = "yonyou_placeholder",
): CustomerImportDraft {
  const customerCode = row.cCusCode?.trim() || "UNKNOWN_CUSTOMER";
  return {
    targetTable: "customers",
    sourceSystem,
    sourceRecordId: customerCode,
    extractedData: {
      customer_code: customerCode,
      full_name: row.cCusName?.trim() || customerCode,
      short_name: row.cCusAbbName?.trim() || undefined,
      address: row.cCusAddress?.trim() || undefined,
      phone: row.cCusPhone?.trim() || undefined,
      credit_level: row.cCusDefine1?.trim() || undefined,
    },
  };
}
