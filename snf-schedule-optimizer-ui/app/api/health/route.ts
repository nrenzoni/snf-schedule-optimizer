import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  let backendStatus = "unknown";

  if (backendUrl) {
    try {
      const res = await fetch(`${backendUrl}/health`, {
        signal: AbortSignal.timeout(5000),
      });
      backendStatus = res.ok ? "healthy" : "unhealthy";
    } catch {
      backendStatus = "unreachable";
    }
  }

  return NextResponse.json({
    status: "ok",
    backend: backendStatus,
  });
}
