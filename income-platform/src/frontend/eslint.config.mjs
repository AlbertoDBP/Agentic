import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import noOffbrandColors from "./eslint-rules/no-offbrand-tailwind-colors.js";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,

  // ── Brand compliance ─────────────────────────────────────────────────────
  // Warns when hardcoded hex / rgb colors appear inside Tailwind arbitrary
  // value classes (e.g. text-[#1A2ECE]).  Developers must use brand tokens.
  {
    plugins: {
      brand: {
        rules: { "no-offbrand-tailwind-colors": noOffbrandColors },
      },
    },
    rules: {
      "brand/no-offbrand-tailwind-colors": "warn",
    },
  },

  // Override default ignores of eslint-config-next.
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
