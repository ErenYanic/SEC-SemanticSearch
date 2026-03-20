import { NextRequest, NextResponse } from "next/server";

import { buildBackendAuthHeaders, getBackendBaseUrl, hasValidAdminSession } from "@/lib/adminAuth";

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  if (!hasValidAdminSession(request)) {
    return NextResponse.json(
      { error: "admin_required", message: "Admin access required." },
      { status: 403 },
    );
  }

  const search = request.nextUrl.search || "";
  const response = await fetch(`${getBackendBaseUrl()}/api/filings/${search}`, {
    method: "DELETE",
    headers: buildBackendAuthHeaders(),
    cache: "no-store",
  });
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}