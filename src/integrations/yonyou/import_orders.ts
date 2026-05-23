export type YonyouSalesOrderRow = {
  cSOCode?: string;
  dDate?: string;
  dPreDate?: string;
  cCusCode?: string;
  cInvCode?: string;
  iQuantity?: string | number;
  iTaxUnitPrice?: string | number;
  iSum?: string | number;
};

export type SalesOrderImportDraft = {
  targetTable: "sales_orders";
  sourceSystem: string;
  sourceRecordId: string;
  extractedData: {
    order_no: string;
    order_date?: string;
    promised_delivery_date?: string;
    customer_source_record_id?: string;
    product_source_record_id?: string;
    quantity?: number;
    unit_price?: number;
    amount_total?: number;
  };
};

function numberOrUndefined(value: string | number | undefined): number | undefined {
  if (value === undefined || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function mapYonyouSalesOrderRow(
  row: YonyouSalesOrderRow,
  sourceSystem = "yonyou_placeholder",
): SalesOrderImportDraft {
  const orderNo = row.cSOCode?.trim() || "UNKNOWN_ORDER";
  return {
    targetTable: "sales_orders",
    sourceSystem,
    sourceRecordId: orderNo,
    extractedData: {
      order_no: orderNo,
      order_date: row.dDate?.trim() || undefined,
      promised_delivery_date: row.dPreDate?.trim() || undefined,
      customer_source_record_id: row.cCusCode?.trim() || undefined,
      product_source_record_id: row.cInvCode?.trim() || undefined,
      quantity: numberOrUndefined(row.iQuantity),
      unit_price: numberOrUndefined(row.iTaxUnitPrice),
      amount_total: numberOrUndefined(row.iSum),
    },
  };
}
