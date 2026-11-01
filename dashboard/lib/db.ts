import { Pool } from "pg";

declare global {
  var deductionDeskDashboardPool: Pool | undefined;
}

if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not configured");

const pool =
  global.deductionDeskDashboardPool ??
  new Pool({ connectionString: process.env.DATABASE_URL, max: 10 });

if (process.env.NODE_ENV !== "production") {
  global.deductionDeskDashboardPool = pool;
}

export default pool;
