// Registers @testing-library/jest-dom matchers (toBeInTheDocument, etc.).
// Loaded for every test file; the matchers are inert in node-environment
// tests and only exercised by component tests that opt into jsdom.
import "@testing-library/jest-dom/vitest";
