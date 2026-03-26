import path from 'node:path';

const OUTPUT_ROOT = path.resolve(process.cwd(), 'output');
const ALLOWED_IMAGE_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.gif',
]);

function normalizeRequestedPath(requestPath: string): string | null {
  const cleanedPath = requestPath.trim().replace(/\\/g, '/');

  if (!cleanedPath || cleanedPath.startsWith('/') || /^[a-zA-Z]:/.test(cleanedPath)) {
    return null;
  }

  const withoutPrefix = cleanedPath
    .replace(/^\.?\//, '')
    .replace(/^output\//i, '');

  const normalized = path.posix.normalize(withoutPrefix);

  if (
    !normalized ||
    normalized === '.' ||
    normalized.startsWith('../') ||
    normalized.includes('\0')
  ) {
    return null;
  }

  return normalized;
}

export function resolveProjectImagePath(requestPath: string): string | null {
  const normalizedPath = normalizeRequestedPath(requestPath);

  if (!normalizedPath) {
    return null;
  }

  const absolutePath = path.resolve(OUTPUT_ROOT, normalizedPath);
  const relativePath = path.relative(OUTPUT_ROOT, absolutePath);

  if (
    !relativePath ||
    relativePath.startsWith('..') ||
    path.isAbsolute(relativePath)
  ) {
    return null;
  }

  if (!ALLOWED_IMAGE_EXTENSIONS.has(path.extname(absolutePath).toLowerCase())) {
    return null;
  }

  return absolutePath;
}

export function getImageContentType(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();

  switch (extension) {
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.webp':
      return 'image/webp';
    case '.gif':
      return 'image/gif';
    default:
      return 'application/octet-stream';
  }
}
