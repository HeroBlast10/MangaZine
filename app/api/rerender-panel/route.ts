import { spawn } from 'node:child_process';

import { NextRequest, NextResponse } from 'next/server';

import type { RerenderRequest, RerenderResponse } from '@/types/comic';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function runPythonRerender(input: RerenderRequest): Promise<RerenderResponse> {
  const pythonExecutable = process.env.PYTHON_EXECUTABLE || 'python';

  return new Promise((resolve, reject) => {
    const child = spawn(
      pythonExecutable,
      ['-m', 'cli.rerender_panel'],
      {
        cwd: process.cwd(),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: process.env,
      },
    );

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => {
      reject(error);
    });

    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || stdout.trim() || `Python exited with code ${code}`));
        return;
      }

      try {
        const response = JSON.parse(stdout) as RerenderResponse;
        resolve(response);
      } catch (error) {
        reject(
          new Error(
            `Invalid rerender response: ${(error as Error).message}\n${stdout.trim()}`,
          ),
        );
      }
    });

    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });
}

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
    const result = await runPythonRerender(body);
    return NextResponse.json(result);
  } catch (error) {
    console.error('[rerender-panel] rerender failed', error);
    return NextResponse.json(
      { error: (error as Error).message || 'Rerender failed.' },
      { status: 500 },
    );
  }
}
