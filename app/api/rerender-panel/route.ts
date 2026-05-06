import { NextRequest, NextResponse } from 'next/server';

import type { RerenderRequest, RerenderResponse } from '@/types/comic';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function isValidRerenderRequest(body: Partial<RerenderRequest>): body is RerenderRequest {
  return Boolean(
    body &&
      body.panel &&
      body.page_id &&
      body.lock_constraints &&
      body.style_pack &&
      body.character_bible,
  );
}

export async function POST(request: NextRequest) {
  let body: Partial<RerenderRequest>;

  try {
    body = (await request.json()) as Partial<RerenderRequest>;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }

  if (!isValidRerenderRequest(body)) {
    return NextResponse.json({ error: 'Invalid rerender request.' }, { status: 400 });
  }

  try {
    const resp = await fetch(`${API_BASE}/api/v1/panel/rerender`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const detail = await resp.text();
      return NextResponse.json(
        { error: detail || `Backend error: ${resp.status}` },
        { status: resp.status },
      );
    }

    const result = (await resp.json()) as RerenderResponse;
    return NextResponse.json(result);
  } catch (error) {
    console.error('[rerender-panel] proxy to FastAPI failed', error);
    return NextResponse.json(
      { error: (error as Error).message || 'Rerender failed.' },
      { status: 502 },
    );
  }
}
