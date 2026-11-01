import { jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

function jwtSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) return null;
  return new TextEncoder().encode(secret);
}

export async function middleware(request: NextRequest) {
  const isApi = request.nextUrl.pathname.startsWith("/api/");
  const authorization = request.headers.get("authorization");
  const token = isApi
    ? authorization?.startsWith("Bearer ")
      ? authorization.slice(7)
      : null
    : request.cookies.get("deductiondesk_token")?.value;
  const secret = jwtSecret();

  if (token && secret) {
    try {
      await jwtVerify(token, secret, { algorithms: ["HS256"] });
      return NextResponse.next();
    } catch {
      // Treat expired or malformed tokens as unauthenticated.
    }
  }

  if (isApi) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/deductions/:path*",
    "/api/deductions/:path*",
    "/api/disputes/:path*",
  ],
};
