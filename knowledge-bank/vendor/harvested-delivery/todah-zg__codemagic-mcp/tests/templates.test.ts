import { describe, it, expect } from "vitest";
import * as yaml from "js-yaml";
import { listYamlTemplateTypes, getYamlTemplate, TEMPLATES } from "../src/templates.js";

// Complete sorted list of known template types.
// This is a strict equality check — if a new template is added to TEMPLATES, update this list too.
// That deliberate friction is the point: it makes new template types visible in CI.
const KNOWN_TYPES = [
  "android", "android-debug", "android-screenshots",
  "dotnet-maui",
  "flutter", "flutter-android-debug", "flutter-native", "flutter-screenshots",
  "ionic-capacitor", "ionic-cordova",
  "ios", "ios-screenshots",
  "kmm",
  "react-native", "react-native-android-debug",
  "snap",
  "unity", "unity-oculus",
];

describe("listYamlTemplateTypes", () => {
  it("returns exactly the known template types", () => {
    expect(listYamlTemplateTypes().sort()).toEqual(KNOWN_TYPES);
  });

  it("matches the TEMPLATES object keys — no drift between source and list", () => {
    expect(Object.keys(TEMPLATES).sort()).toEqual(KNOWN_TYPES);
  });
});

describe("getYamlTemplate", () => {
  it("returns a string for every listed type", () => {
    for (const type of listYamlTemplateTypes()) {
      expect(getYamlTemplate(type)).toBeTruthy();
    }
  });

  it("returns null for an unknown project type", () => {
    expect(getYamlTemplate("unknown-type")).toBeNull();
  });

  it("every template is parseable YAML", () => {
    for (const type of listYamlTemplateTypes()) {
      const template = getYamlTemplate(type)!;
      expect(() => yaml.load(template)).not.toThrow();
    }
  });

  it("every template contains a workflows key", () => {
    for (const type of listYamlTemplateTypes()) {
      const template = getYamlTemplate(type)!;
      const parsed = yaml.load(template) as Record<string, unknown>;
      expect(parsed).toHaveProperty("workflows");
    }
  });
});