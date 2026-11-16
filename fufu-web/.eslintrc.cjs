/**
 * ESLint 配置（ESLint 8 · .eslintrc 格式）
 *
 * 规则强度刻意保守：这个项目是既有代码库，一上来开到 error 级会
 * 淹没有价值的问题。所以：
 *   - react-hooks 规则 = warn（Hooks 顺序错误是真的会白屏的，值得关注）
 *   - 未使用变量 = warn
 *   - any = 关掉（改造期大量 any，全部改完不现实，先不噪音轰炸）
 * 等现有告警清完再逐步收紧。
 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint', 'react-hooks', 'react-refresh'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
  ],
  settings: {
    react: { version: '18.3' },
  },
  ignorePatterns: ['dist', 'node_modules', '*.config.js', '*.config.ts', 'vite.config.ts'],
  rules: {
    // ── React Hooks：违反会导致 "Rendered fewer hooks than expected" 直接崩页 ──
    'react-hooks/rules-of-hooks': 'warn',
    'react-hooks/exhaustive-deps': 'warn',

    // ── TypeScript ──
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/no-non-null-assertion': 'off',

    // ── 通用 ──
    // 允许 warn/error/info，但业务代码里散落的 console.log 会被拦下
    'no-console': ['warn', { allow: ['warn', 'error', 'info'] }],
    'no-empty': ['warn', { allowEmptyCatch: true }],
    'no-undef': 'off', // TS 已经覆盖，交给 tsc 更准
    eqeqeq: ['warn', 'smart'],
    'prefer-const': 'warn',

    // ── 热更新友好性 ──
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
  },
  overrides: [
    {
      // 脚本/配置类文件允许 console
      files: ['src/main.tsx', 'src/lib/**/*.ts'],
      rules: { 'no-console': 'off' },
    },
  ],
};
