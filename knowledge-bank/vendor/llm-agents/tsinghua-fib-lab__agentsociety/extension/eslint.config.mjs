import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

const tsFiles = ["src/**/*.ts"];

export default [
  {
    ignores: ["out", "dist", "**/*.d.ts", "**/*.js"],
  },
  {
    ...js.configs.recommended,
    files: tsFiles,
  },
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: tsFiles,
  })),
  {
    files: tsFiles,
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "module",
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },
    rules: {
      // This extension passes a large amount of dynamic JSON/webview payloads
      // and uses a few VSCode-oriented escape hatches. Keep lint focused on
      // actionable issues instead of forcing broad type rewrites.
      "@typescript-eslint/ban-ts-comment": "off",
      "@typescript-eslint/naming-convention": [
        "warn",
        {
          selector: "import",
          format: ["camelCase", "PascalCase"],
        },
      ],
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/no-unused-vars": "off",
      curly: "warn",
      eqeqeq: "warn",
      "no-throw-literal": "warn",
      "no-useless-assignment": "off",
      "preserve-caught-error": "off",
      semi: "off",
    },
  },
];
