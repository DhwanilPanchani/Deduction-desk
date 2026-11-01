import { Pool } from "pg";

declare global {
  var deductionDeskPool: Pool | undefined;
}

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not configured");
}

const pool =
  global.deductionDeskPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 10,
  });

if (process.env.NODE_ENV !== "production") {
  global.deductionDeskPool = pool;
}

export default pool;
