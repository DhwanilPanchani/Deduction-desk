import { jwtVerify } from "jose";

import pool from "@/lib/db";

function jwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) throw new Error("JWT_SECRET is not configured");
  return new TextEncoder().encode(secret);
}

async function authorize(request: Request) {
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer ")) return false;
  try {
    await jwtVerify(authorization.slice(7), jwtSecret(), { algorithms: ["HS256"] });
    return true;
  } catch {
    return false;
  }
}

let schemaPromise: Promise<void> | null = null;

function ensureDisputeSchema() {
  if (!schemaPromise) {
    schemaPromise = pool
      .query(`
        ALTER TABLE disputes ADD COLUMN IF NOT EXISTS packet_content TEXT;
        ALTER TABLE disputes ADD COLUMN IF NOT EXISTS filed_at TIMESTAMPTZ;
        ALTER TABLE disputes ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'submitted';
        ALTER TABLE disputes ADD COLUMN IF NOT EXISTS claimed_amount NUMERIC(14, 2);
        ALTER TABLE disputes ADD COLUMN IF NOT EXISTS agent_confidence NUMERIC(5, 4);
      `)
      .then(() => undefined)
      .catch((error) => {
        schemaPromise = null;
        throw error;
      });
  }
  return schemaPromise;
}

export async function POST(request: Request) {
  if (!(await authorize(request))) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const deductionId = Number(body.deduction_id);
  const claimedAmount = Number(body.claimed_amount);
  const agentConfidence = Number(body.agent_confidence);
  const packetMarkdown = body.packet_markdown;
  if (
    !Number.isInteger(deductionId) ||
    deductionId <= 0 ||
    typeof packetMarkdown !== "string" ||
    !packetMarkdown.trim() ||
    !Number.isFinite(claimedAmount) ||
    claimedAmount < 0 ||
    !Number.isFinite(agentConfidence) ||
    agentConfidence < 0 ||
    agentConfidence > 1
  ) {
    return Response.json({ error: "Invalid dispute payload" }, { status: 400 });
  }

  await ensureDisputeSchema();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await client.query(
      `INSERT INTO disputes
        (deduction_id, opened_at, packet_content, filed_at, status, claimed_amount, agent_confidence)
       VALUES ($1, NOW(), $2, NOW(), 'submitted', $3, $4)
       ON CONFLICT (deduction_id) DO UPDATE SET
         packet_content = EXCLUDED.packet_content,
         filed_at = EXCLUDED.filed_at,
         status = 'submitted',
         claimed_amount = EXCLUDED.claimed_amount,
         agent_confidence = EXCLUDED.agent_confidence
       RETURNING id, deduction_id, packet_content, filed_at, status,
                 claimed_amount, agent_confidence, created_at`,
      [deductionId, packetMarkdown, claimedAmount, agentConfidence],
    );
    const update = await client.query(
      "UPDATE deductions SET status='disputed' WHERE id=$1 RETURNING id",
      [deductionId],
    );
    if (!update.rowCount) {
      throw new Error(`Deduction ${deductionId} does not exist`);
    }
    await client.query("COMMIT");
    return Response.json({ dispute: result.rows[0] }, { status: 201 });
  } catch (error) {
    await client.query("ROLLBACK");
    console.error("Failed to file dispute", error);
    return Response.json({ error: "Unable to file dispute" }, { status: 500 });
  } finally {
    client.release();
  }
}

export async function GET(request: Request) {
  if (!(await authorize(request))) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  await ensureDisputeSchema();
  const result = await pool.query(`
    SELECT dp.id, dp.deduction_id, d.deduction_number, r.name AS retailer,
           d.type AS deduction_type, dp.claimed_amount, dp.agent_confidence,
           dp.packet_content, dp.filed_at, dp.status, dp.created_at
    FROM disputes dp
    JOIN deductions d ON d.id=dp.deduction_id
    JOIN invoices i ON i.id=d.invoice_id
    JOIN purchase_orders po ON po.id=i.purchase_order_id
    JOIN retailers r ON r.id=po.retailer_id
    ORDER BY dp.filed_at DESC, dp.id DESC
  `);
  return Response.json({ data: result.rows, total: result.rowCount });
}
