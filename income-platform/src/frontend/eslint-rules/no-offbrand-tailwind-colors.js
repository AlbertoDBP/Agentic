/**
 * ESLint rule: no-offbrand-tailwind-colors
 * ==========================================
 * Prevents arbitrary Tailwind color values in JSX className attributes
 * that bypass the CSS token system.
 *
 * ✗  className="text-[#1A2ECE]"          — hardcoded hex
 * ✗  className="bg-[rgb(26,46,206)]"      — hardcoded rgb
 * ✓  className="text-primary"             — token
 * ✓  className="bg-[var(--imc-azul)]"     — CSS variable reference
 *
 * Add to eslint.config.mjs:
 *   import noOffbrand from './eslint-rules/no-offbrand-tailwind-colors.js'
 *
 *   {
 *     plugins: { brand: { rules: { 'no-offbrand-tailwind-colors': noOffbrand } } },
 *     rules: { 'brand/no-offbrand-tailwind-colors': 'warn' }
 *   }
 */

const HEX_IN_BRACKETS      = /\[#[0-9a-fA-F]{3,8}\]/;
const RGB_IN_BRACKETS       = /\[rgba?\(/i;
const HSL_IN_BRACKETS       = /\[hsla?\(/i;
const CSS_VAR_IN_BRACKETS   = /\[var\(--/;

function containsHardcodedColor(str) {
  if (CSS_VAR_IN_BRACKETS.test(str)) return false; // var(--token) is OK
  return HEX_IN_BRACKETS.test(str) || RGB_IN_BRACKETS.test(str) || HSL_IN_BRACKETS.test(str);
}

/** @type {import('eslint').Rule.RuleModule} */
const rule = {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Disallow hardcoded color values in Tailwind arbitrary value syntax. " +
        "Use CSS custom property tokens instead.",
      recommended: false,
    },
    schema: [],
    messages: {
      hardcodedColor:
        "Off-brand color '{{ value }}' found in Tailwind class. " +
        "Use a brand token class (e.g. text-primary) or var(--color-*) instead.",
    },
  },

  create(context) {
    function checkNode(node) {
      // JSX className="..." (Literal)
      if (node.type === "Literal" && typeof node.value === "string") {
        const classes = node.value.split(/\s+/);
        for (const cls of classes) {
          if (containsHardcodedColor(cls)) {
            context.report({
              node,
              messageId: "hardcodedColor",
              data: { value: cls },
            });
          }
        }
        return;
      }

      // Template literal: className={`text-[#fff] ...`}
      if (node.type === "TemplateLiteral") {
        for (const quasi of node.quasis) {
          const classes = quasi.value.raw.split(/\s+/);
          for (const cls of classes) {
            if (containsHardcodedColor(cls)) {
              context.report({
                node,
                messageId: "hardcodedColor",
                data: { value: cls },
              });
            }
          }
        }
      }
    }

    return {
      // className="..."
      JSXAttribute(node) {
        if (node.name.name !== "className") return;
        if (!node.value) return;

        if (node.value.type === "Literal") {
          checkNode(node.value);
        } else if (node.value.type === "JSXExpressionContainer") {
          const expr = node.value.expression;
          if (expr.type === "Literal" || expr.type === "TemplateLiteral") {
            checkNode(expr);
          }
          // Handle cn('text-[#hex]', ...) call expressions
          if (expr.type === "CallExpression") {
            for (const arg of expr.arguments) {
              if (arg.type === "Literal" || arg.type === "TemplateLiteral") {
                checkNode(arg);
              }
            }
          }
        }
      },
    };
  },
};

export default rule;
