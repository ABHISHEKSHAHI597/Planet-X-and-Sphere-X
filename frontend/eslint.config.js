import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "dist-mock", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // workflow.md §3: the frontend never calls external services except Aladin's HiPS tiles.
      "no-restricted-syntax": ["error", {
        selector: "Literal[value=/irsa\\.ipac|simbad\\.|ssd\\.jpl\\.nasa|imcce\\.fr|nasa-irsa-spherex/]",
        message: "The frontend must not call IRSA/SIMBAD/Horizons/SkyBoT/S3 directly; go through /api/v1.",
      }],
    },
  },
  // Credits link to the archives' acknowledgement pages for humans; nothing there is fetched.
  { files: ["src/content/credits.ts"], rules: { "no-restricted-syntax": "off" } },
  { files: ["scripts/**/*.mjs"], languageOptions: { globals: globals.node } },
);
