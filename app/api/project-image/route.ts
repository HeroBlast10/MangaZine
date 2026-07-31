import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

export async function GET(request: NextRequest) {
  const requestedPath = request.nextUrl.searchParams.get('path');

  if (!requestedPath) {
    return NextResponse.json({ error: 'Missing image path.' }, { status: 400 });
  }

  try {
    const backendUrl = new URL('/api/v1/image', API_BASE);
    backendUrl.searchParams.set('path', requestedPath);
    const response = await fetch(backendUrl, {
      headers: process.env.MANGAZINE_API_KEY
        ? { 'X-API-Key': process.env.MANGAZINE_API_KEY }
        : {},
      cache: 'no-store',
      signal: request.signal,
    });

    if (!response.ok || !response.body) {
      const detail = await response.text();
      return NextResponse.json(
        { error: detail || 'Image not found.' },
        { status: response.status },
      );
    }

    return new NextResponse(response.body, {
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
        'Cache-Control': 'private, max-age=300',
      },
    });
  } catch (error) {
    console.error('[project-image] proxy failed', error);
    return NextResponse.json({ error: 'Failed to load image.' }, { status: 502 });
  }
}
