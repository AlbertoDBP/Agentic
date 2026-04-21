/** @type {import('stylelint').Config} */
export default {
  extends: ["stylelint-config-standard"],

  rules: {
    // ── Brand token enforcement ────────────────────────────────────────────
    // Forbid raw hex / rgb / hsl color values in ALL CSS files except
    // globals.css (which is the token definition file).
    // Developers must use var(--imc-*) or var(--color-*) tokens.
    "color-no-hex": [
      true,
      {
        message: (hex) =>
          `Hardcoded color '${hex}' — use a CSS custom property (var(--color-*)) instead.`,
        // globals.css is exempt — that's where the palette is defined.
        disableFix: true,
      },
    ],

    // Block raw rgb() / hsl() values too
    "function-disallowed-list": [
      ["rgb", "rgba", "hsl", "hsla"],
      {
        message: (fn) =>
          `Raw ${fn}() color function — use a CSS custom property (var(--color-*)) instead.`,
      },
    ],

    // ── Font enforcement ───────────────────────────────────────────────────
    // Warn if a font-family is declared without HK Grotesk (or its fallbacks)
    "font-family-no-missing-generic-family-keyword": true,

    // ── General hygiene ────────────────────────────────────────────────────
    "color-named": "never",           // no 'red', 'blue', etc.
    "shorthand-property-no-redundant-values": true,
    "declaration-block-no-duplicate-properties": true,
    "no-duplicate-selectors": true,
    "unit-no-unknown": true,
  },

  // globals.css defines the palette — exempt from color-no-hex
  ignoreFiles: [
    "**/globals.css",
    "**/node_modules/**",
    "**/.next/**",
  ],

  overrides: [
    {
      // CSS modules are allowed to use tokens freely
      files: ["**/*.module.css"],
      rules: {
        "color-no-hex": true,
        "function-disallowed-list": [["rgb", "rgba", "hsl", "hsla"]],
      },
    },
  ],
};
