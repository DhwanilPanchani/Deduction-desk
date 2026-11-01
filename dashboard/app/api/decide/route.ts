import pool from "@/lib/db";
import { ensureReviewSchema, getDeductionDetail } from "@/lib/data";

async function fileDispute(detail: Record<string, unknown>) {
  const portalUrl = process.env.PORTAL_URL ?? "http://localhost:3000";
  const auth = await fetch(`${portalUrl}/api/auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "supplier_demo", password: "glimpse2026" }),
  });
  if (!auth.ok) throw new Error(`Portal authentication failed (${auth.status})`);
  const { token } = await auth.json();
  const amount = Number(detail.claimed_amount);
  const actualShort = Math.max(0, Number(detail.invoiced_qty) - Number(detail.delivered_qty));
  const promotionEvidence = detail.promotion_name
    ? `Authorized promotion '${detail.promotion_name}' matched the invoice date.`
    : `No authorized promotion matched retailer ${detail.retailer}, SKU ${detail.product_sku}, and invoice date ${String(detail.invoice_date).slice(0, 10)}.`;
  const packet = `# Deduction Dispute Packet

| Field | Value |
|---|---|
| Deduction ID | ${detail.deduction_number} (internal ID ${detail.id}) |
| Retailer | ${detail.retailer} |
| Deduction Type | ${detail.type} |
| Claimed Amount | $${amount.toFixed(2)} |
| Invoice | ${detail.invoice_number} |
| Purchase Order | ${detail.po_number} |

## Basis for Dispute

${detail.reasoning}

## Evidence

- Invoice quantity: ${detail.invoiced_qty}; POD delivered quantity: ${detail.delivered_qty}; calculated shortage: ${actualShort}.
- ${promotionEvidence}
- Invoice unit price: $${Number(detail.invoice_unit_price).toFixed(2)}; PO unit price: $${Number(detail.po_unit_price).toFixed(2)}.

## Requested Resolution

Please reverse the unsupported deduction of **$${amount.toFixed(2)}** and remit the withheld amount.

---

_AI-assisted review with human approval. Agent confidence: ${(Number(detail.confidence) * 100).toFixed(1)}%._
`;
  const response = await fetch(`${portalUrl}/api/disputes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ deduction_id: detail.id, packet_markdown: packet, claimed_amount: amount, agent_confidence: Number(detail.confidence) }),
  });
  if (!response.ok) throw new Error(`Portal filing failed (${response.status}): ${await response.text()}`);
  return response.json();
}

export async function POST(request: Request) {
  await ensureReviewSchema();
  let body: Record<string, unknown>;
  try { body = await request.json(); } catch { return Response.json({ error: "Invalid JSON body" }, { status: 400 }); }
  const deductionId = Number(body.deduction_id);
  const finalIsValid = body.final_is_valid;
  const overridden = body.overridden;
  const humanNote = body.human_note;
  if (!Number.isInteger(deductionId) || typeof finalIsValid !== "boolean" || typeof overridden !== "boolean" || (overridden && (typeof humanNote !== "string" || !humanNote.trim()))) {
    return Response.json({ error: "Invalid review payload" }, { status: 400 });
  }
  const detail = await getDeductionDetail(deductionId);
  if (!detail) return Response.json({ error: "Deduction not found" }, { status: 404 });
  if (overridden !== (finalIsValid !== detail.agent_is_valid)) {
    return Response.json({ error: "Override flag does not match the final verdict" }, { status: 400 });
  }

  try {
    // In DeductionDesk, is_valid=false means the retailer deduction is unsupported
    // and therefore dispute-worthy. File before removing the item from review.
    let filing = null;
    if (!finalIsValid) filing = await fileDispute(detail);
    const result = await pool.query(
      `INSERT INTO human_reviews (deduction_id, final_is_valid, overridden, human_note)
       VALUES ($1,$2,$3,$4)
       ON CONFLICT (deduction_id) DO UPDATE SET
         final_is_valid=EXCLUDED.final_is_valid, overridden=EXCLUDED.overridden,
         human_note=EXCLUDED.human_note, reviewed_at=NOW()
       RETURNING *`,
      [deductionId, finalIsValid, overridden, typeof humanNote === "string" ? humanNote.trim() : null],
    );
    return Response.json({ review: result.rows[0], filing });
  } catch (error) {
    console.error("Review decision failed", error);
    return Response.json({ error: error instanceof Error ? error.message : "Decision failed" }, { status: 502 });
  }
}
