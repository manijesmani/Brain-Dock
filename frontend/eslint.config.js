import js from "@eslint/js";
import prettierConfig from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },

  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      // Type-aware rule sets. These need a TypeScript program, which is what
      // makes them able to catch unhandled promises and unsafe `any` flowing
      // through the code -- the reason ESLint is used here at all.
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // The project bans `any` outright rather than merely discouraging it.
      "@typescript-eslint/no-explicit-any": "error",
    },
  },

  // The ESLint config itself runs in Node and is not covered by a tsconfig,
  // so type-aware rules cannot apply to it.
  {
    files: ["eslint.config.js"],
    languageOptions: { globals: globals.node },
    extends: [tseslint.configs.disableTypeChecked],
  },

  // Must stay last so formatting-related rules are switched off in favour of
  // Prettier.
  prettierConfig,
);
