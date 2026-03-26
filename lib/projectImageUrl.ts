import type { RenderOutput } from '@/types/comic';

export function buildProjectImageUrl(rawPath: string): string {
  const normalizedPath = rawPath
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\.?\//, '');

  return `/api/project-image?${new URLSearchParams({
    path: normalizedPath,
  }).toString()}`;
}

export function getLocalImagePath(renderOutput?: RenderOutput | null): string | null {
  const localImagePath = renderOutput?.generation_params?.local_image_path;

  return typeof localImagePath === 'string' && localImagePath.trim()
    ? localImagePath
    : null;
}

export function resolveRenderImageUrl(renderOutput?: RenderOutput | null): string | null {
  if (!renderOutput) {
    return null;
  }

  if (typeof renderOutput.image_url === 'string' && renderOutput.image_url.trim()) {
    return renderOutput.image_url;
  }

  const localImagePath = getLocalImagePath(renderOutput);

  return localImagePath ? buildProjectImageUrl(localImagePath) : null;
}
