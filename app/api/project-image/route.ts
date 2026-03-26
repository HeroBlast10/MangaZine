import { promises as fs } from 'node:fs';

import { NextRequest, NextResponse } from 'next/server';

import { getImageContentType, resolveProjectImagePath } from '@/lib/projectImageServer';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const requestedPath = request.nextUrl.searchParams.get('path');

  if (!requestedPath) {
    return NextResponse.json({ error: 'Missing image path.' }, { status: 400 });
  }

  const imagePath = resolveProjectImagePath(requestedPath);

  if (!imagePath) {
    return NextResponse.json({ error: 'Invalid image path.' }, { status: 400 });
  }

  try {
    const imageBuffer = await fs.readFile(imagePath);

    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': getImageContentType(imagePath),
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return NextResponse.json({ error: 'Image not found.' }, { status: 404 });
    }

    console.error('[project-image] failed to read image', error);
    return NextResponse.json({ error: 'Failed to read image.' }, { status: 500 });
  }
}
