import { NextRequest, NextResponse } from "next/server";

import { buildBackendAuthHeaders, getBackendBaseUrl, hasValidAdminSession } from "@/lib/adminAuth";

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!hasValidAdminSession(request)) {
    return NextResponse.json(
      { error: "admin_required", message: "Admin access required." },
      { status: 403 },
    );
  }

  const body = await request.text();
  const response = await fetch(`${getBackendBaseUrl()}/api/filings/bulk-delete`, {
    method: "POST",
    headers: buildBackendAuthHeaders(),
    body,
    cache: "no-store",
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}