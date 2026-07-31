import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      "@next/next/no-img-element": "off",
    },
  },
  globalIgnores([
    ".next/**",
    ".pytest_cache/",
    ".cursor/",
    "out/**",
    "output/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);
