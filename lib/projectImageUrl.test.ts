import { describe, expect, it } from "vitest";

import {
  buildProjectImageUrl,
  getLocalImagePath,
  resolveRenderImageUrl,
} from "./projectImageUrl";

describe("project image URL helpers", () => {
  it("normalizes Windows paths before encoding them", () => {
    expect(buildProjectImageUrl(String.raw`.\output\project\panel.png`)).toBe(
      "/api/project-image?path=output%2Fproject%2Fpanel.png",
    );
  });

  it("prefers a provider URL over a local path", () => {
    expect(
      resolveRenderImageUrl({
        status: "draft_ready",
        image_url: "https://cdn.example/panel.png",
        generation_params: { local_image_path: "output/panel.png" },
      }),
    ).toBe("https://cdn.example/panel.png");
  });

  it("falls back to a proxied local image path", () => {
    expect(
      resolveRenderImageUrl({
        status: "draft_ready",
        generation_params: { local_image_path: "output/panel.png" },
      }),
    ).toBe("/api/project-image?path=output%2Fpanel.png");
  });

  it("rejects missing and blank local paths", () => {
    expect(getLocalImagePath()).toBeNull();
    expect(
      getLocalImagePath({
        status: "pending",
        generation_params: { local_image_path: " " },
      }),
    ).toBeNull();
  });
});
