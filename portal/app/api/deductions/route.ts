import { jwtVerify } from "jose";

import pool from "@/lib/db";

const ALLOWED_STATUSES = new Set(["pending", "disputed", "accepted"]);
const ALLOWED_TYPES = new Set([
  "shortage",
  "pricing",
  "promotional",
  "compliance",
  "damage",
]);

function jwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET is not configured");
  }
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

export async function GET(request: Request) {
  if (!(await authorize(request))) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const retailer = searchParams.get("retailer")?.trim() || null;
  const status = searchParams.get("status")?.trim().toLowerCase() || null;
  const type = searchParams.get("type")?.trim().toLowerCase() || null;
  const requestedPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const requestedPageSize = Number.parseInt(searchParams.get("page_size") ?? "50", 10);
  const page = Number.isFinite(requestedPage) ? Math.max(1, requestedPage) : 1;
  const pageSize = Number.isFinite(requestedPageSize)
    ? Math.min(100, Math.max(1, requestedPageSize))
    : 50;

  if (status && !ALLOWED_STATUSES.has(status)) {
    return Response.json({ error: "Invalid status filter" }, { status: 400 });
  }
  if (type && !ALLOWED_TYPES.has(type)) {
    return Response.json({ error: "Invalid type filter" }, { status: 400 });
  }

  const values: string[] = [];
  const conditions: string[] = [];

  if (retailer) {
    values.push(retailer);
    conditions.push(`r.name = $${values.length}`);
  }
  if (status) {
    values.push(status);
    conditions.push(`d.status = $${values.length}`);
  }
  if (type) {
    values.push(type);
    conditions.push(`d.type = $${values.length}`);
  }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const from = `
    FROM deductions d
    JOIN invoices i ON i.id = d.invoice_id
    JOIN purchase_orders po ON po.id = i.purchase_order_id
    JOIN retailers r ON r.id = po.retailer_id
  `;

  try {
    const countResult = await pool.query<{ count: string }>(
      `SELECT COUNT(*)::text AS count ${from} ${where}`,
      values,
    );
    const total = Number(countResult.rows[0].count);
    const dataValues: Array<string | number> = [...values, pageSize, (page - 1) * pageSize];
    const limitParameter = values.length + 1;
    const offsetParameter = values.length + 2;
    const result = await pool.query(
      `SELECT
        d.id,
        d.deduction_number,
        i.id AS invoice_id,
        i.invoice_number,
        i.gross_amount AS invoice_amount,
        r.name AS retailer,
        r.name AS retailer_name,
        d.type,
        d.type AS deduction_type,
        d.amount AS claimed_amount,
        d.status,
        d.retailer_notes,
        d.claim_date
      ${from}
      ${where}
      ORDER BY d.claim_date DESC, d.id DESC
      LIMIT $${limitParameter} OFFSET $${offsetParameter}`,
      dataValues,
    );

    return Response.json({
      data: result.rows,
      pagination: {
        page,
        page_size: pageSize,
        total,
        total_pages: Math.ceil(total / pageSize),
      },
      filters: { retailer, status, type },
    });
  } catch (error) {
    console.error("Failed to fetch deductions", error);
    return Response.json({ error: "Unable to fetch deductions" }, { status: 500 });
  }
}
