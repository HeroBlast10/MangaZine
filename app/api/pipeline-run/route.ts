import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

function backendHeaders(): HeadersInit {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (process.env.MANGAZINE_API_KEY) {
    headers['X-API-Key'] = process.env.MANGAZINE_API_KEY;
  }
  return headers;
}

export async function POST(request: NextRequest) {
  let rawBody: string;
  try {
    rawBody = await request.text();
    JSON.parse(rawBody);
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/pipeline/run`, {
      method: 'POST',
      headers: backendHeaders(),
      body: rawBody,
      cache: 'no-store',
      signal: request.signal,
    });

    if (!response.ok || !response.body) {
      const detail = await response.text();
      return NextResponse.json(
        { error: detail || `Backend error: ${response.status}` },
        { status: response.status },
      );
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      return new Response(null, { status: 499 });
    }
    console.error('[pipeline-run] proxy to FastAPI failed', error);
    return NextResponse.json(
      { error: (error as Error).message || 'Pipeline request failed.' },
      { status: 502 },
    );
  }
}
