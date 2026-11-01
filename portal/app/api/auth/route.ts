import { SignJWT } from "jose";

const TEST_USERNAME = "supplier_demo";
const TEST_PASSWORD = "glimpse2026";

function jwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error("JWT_SECRET is not configured");
  }
  return new TextEncoder().encode(secret);
}

export async function POST(request: Request) {
  let credentials: { username?: unknown; password?: unknown };

  try {
    credentials = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (
    credentials.username !== TEST_USERNAME ||
    credentials.password !== TEST_PASSWORD
  ) {
    return Response.json({ error: "Invalid credentials" }, { status: 401 });
  }

  const token = await new SignJWT({ username: TEST_USERNAME, role: "supplier" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(TEST_USERNAME)
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(jwtSecret());

  return Response.json({ token, expires_in: 3600, token_type: "Bearer" });
}
