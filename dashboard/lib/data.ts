import pool from "@/lib/db";

export const REVIEW_DDL = `
  CREATE TABLE IF NOT EXISTS human_reviews (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL UNIQUE REFERENCES deductions(id) ON DELETE CASCADE,
    final_is_valid BOOLEAN NOT NULL,
    overridden BOOLEAN NOT NULL,
    human_note TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE TABLE IF NOT EXISTS agent_llm_calls (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL REFERENCES deductions(id) ON DELETE CASCADE,
    call_number INTEGER NOT NULL CHECK (call_number BETWEEN 1 AND 3),
    is_valid BOOLEAN NOT NULL,
    reasoning TEXT NOT NULL,
    raw_response TEXT,
    is_replay BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (deduction_id, call_number)
  );
  CREATE TABLE IF NOT EXISTS extracted_documents (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL UNIQUE REFERENCES deductions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    difficulty_tier TEXT NOT NULL,
    layout_type TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
`;

let schemaReady: Promise<void> | null = null;

export function ensureReviewSchema() {
  if (!schemaReady) {
    schemaReady = pool.query(REVIEW_DDL).then(() => undefined).catch((error) => {
      schemaReady = null;
      throw error;
    });
  }
  return schemaReady;
}

export type QueueItem = {
  id: string;
  deduction_number: string;
  retailer: string;
  type: string;
  claimed_amount: string;
  agent_is_valid: boolean;
  confidence: string;
  reasoning: string;
  method: string;
  priority_score: string;
};

const SORTS: Record<string, string> = {
  priority: "priority_score DESC, d.id DESC",
  amount: "d.amount DESC, d.id DESC",
  confidence: "ad.confidence ASC, d.id DESC",
};

export async function getQueue(sort = "priority"): Promise<QueueItem[]> {
  await ensureReviewSchema();
  const orderBy = SORTS[sort] ?? SORTS.priority;
  const result = await pool.query<QueueItem>(`
    SELECT d.id, d.deduction_number, r.name AS retailer, d.type,
           d.amount AS claimed_amount, ad.is_valid AS agent_is_valid,
           ad.confidence, ad.reasoning, ad.method,
           ROUND(d.amount * (1 - ad.confidence), 2) AS priority_score
    FROM agent_decisions ad
    JOIN deductions d ON d.id=ad.deduction_id
    JOIN invoices i ON i.id=d.invoice_id
    JOIN purchase_orders po ON po.id=i.purchase_order_id
    JOIN retailers r ON r.id=po.retailer_id
    LEFT JOIN disputes dp ON dp.deduction_id=d.id
    LEFT JOIN human_reviews hr ON hr.deduction_id=d.id
    WHERE ad.needs_human_review=TRUE
      AND dp.id IS NULL
      AND hr.id IS NULL
    ORDER BY ${orderBy}
  `);
  return result.rows;
}

export async function getDeductionDetail(id: number) {
  await ensureReviewSchema();
  const result = await pool.query(
    `SELECT d.id, d.deduction_number, d.type, d.status, d.amount AS claimed_amount,
            d.claimed_qty, d.claimed_unit_price, d.claim_date, d.retailer_notes,
            ad.is_valid AS agent_is_valid, ad.confidence, ad.reasoning, ad.method,
            ad.needs_human_review, r.name AS retailer, i.id AS invoice_id,
            i.invoice_number, i.invoice_date, i.invoiced_qty,
            i.unit_price AS invoice_unit_price, i.gross_amount AS invoice_amount,
            po.po_number, po.product_sku, po.product_name, po.unit_price AS po_unit_price,
            po.expected_delivery_date, pod.delivered_qty, pod.damaged_qty,
            pod.delivery_date, promo.promotion_name, promo.discount_percent,
            promo.start_date AS promotion_start_date, promo.end_date AS promotion_end_date,
            ed.extraction_method, ed.difficulty_tier, ed.filename AS document_filename
     FROM deductions d
     JOIN agent_decisions ad ON ad.deduction_id=d.id
     JOIN invoices i ON i.id=d.invoice_id
     JOIN purchase_orders po ON po.id=i.purchase_order_id
     JOIN retailers r ON r.id=po.retailer_id
     JOIN proof_of_delivery pod ON pod.purchase_order_id=po.id
     LEFT JOIN extracted_documents ed ON ed.deduction_id=d.id
     LEFT JOIN LATERAL (
       SELECT tp.promotion_name, tp.discount_percent, tp.start_date, tp.end_date
       FROM trade_promotions tp
       WHERE tp.brand_id=po.brand_id AND tp.retailer_id=po.retailer_id
         AND tp.product_sku=po.product_sku
         AND i.invoice_date BETWEEN tp.start_date AND tp.end_date
       ORDER BY tp.start_date DESC LIMIT 1
     ) promo ON TRUE
     WHERE d.id=$1`,
    [id],
  );
  if (!result.rows[0]) return null;
  const calls = await pool.query(
    `SELECT call_number, is_valid, reasoning, is_replay, created_at
     FROM agent_llm_calls WHERE deduction_id=$1 ORDER BY call_number`,
    [id],
  );
  return { ...result.rows[0], calls: calls.rows };
}
