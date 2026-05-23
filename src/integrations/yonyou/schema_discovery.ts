export type YonyouSourceKind = "u8" | "u9" | "nc" | "unknown";

export type SchemaDiscoveryConfig = {
  sourceSystem: string;
  sourceKind: YonyouSourceKind;
  candidateTables: string[];
  requiredBusinessObjects: string[];
};

export type SchemaDiscoveryPlan = {
  sourceSystem: string;
  sourceKind: YonyouSourceKind;
  steps: string[];
  candidateTables: string[];
  outputTables: string[];
};

export function buildSchemaDiscoveryPlan(config: SchemaDiscoveryConfig): SchemaDiscoveryPlan {
  return {
    sourceSystem: config.sourceSystem,
    sourceKind: config.sourceKind,
    candidateTables: config.candidateTables,
    outputTables: ["external_source_mappings", "ai_extraction_queue"],
    steps: [
      "Collect exported table dictionaries or screenshots from the customer.",
      "Confirm customer, order, product, and inventory table ownership with a human reviewer.",
      "Map source primary keys into external_source_mappings.",
      "Write uncertain records into ai_extraction_queue for review before any business-table insert.",
    ],
  };
}

export const defaultDiscoveryPlan = buildSchemaDiscoveryPlan({
  sourceSystem: "yonyou_placeholder",
  sourceKind: "unknown",
  candidateTables: ["Customer", "Inventory", "SO_SOMain", "SO_SODetails", "CurrentStock"],
  requiredBusinessObjects: ["customers", "sales_orders", "products", "inventory"],
});
