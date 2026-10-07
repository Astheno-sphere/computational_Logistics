import { describe, it, expect } from "vitest";
import { detectProjectType } from "../src/detection.js";

describe("detectProjectType", () => {

  it("detects Flutter from pubspec.yaml", () => {
    const result = detectProjectType(["pubspec.yaml", "lib/main.dart", "android/", "ios/"]);
    expect(result.projectType).toBe("flutter");
    expect(result.confidence).toBe("high");
  });

  it("detects flutter-native from .android directory", () => {
    const result = detectProjectType(["pubspec.yaml", ".android/Flutter/", ".ios/", "lib/"]);
    expect(result.projectType).toBe("flutter-native");
    expect(result.confidence).toBe("high");
  });

  it("detects React Native from metro.config.js", () => {
    const result = detectProjectType(["package.json", "metro.config.js", "android/", "ios/"]);
    expect(result.projectType).toBe("react-native");
    expect(result.confidence).toBe("high");
  });

  it("detects React Native from package.json dependencies", () => {
    const pkg = JSON.stringify({ dependencies: { "react-native": "0.72.0" } });
    const result = detectProjectType(["package.json", "android/", "ios/"], pkg);
    expect(result.projectType).toBe("react-native");
    expect(result.confidence).toBe("high");
  });

  it("detects Expo from package.json dependencies", () => {
    const pkg = JSON.stringify({ dependencies: { "expo": "~49.0.0" } });
    const result = detectProjectType(["package.json", "app.json"], pkg);
    expect(result.projectType).toBe("react-native");
    expect(result.confidence).toBe("high");
  });

  it("detects Ionic Capacitor", () => {
    const result = detectProjectType(["package.json", "capacitor.config.ts", "src/"]);
    expect(result.projectType).toBe("ionic-capacitor");
    expect(result.confidence).toBe("high");
  });

  it("detects Ionic Cordova", () => {
    const result = detectProjectType(["package.json", "config.xml", "www/"]);
    expect(result.projectType).toBe("ionic-cordova");
    expect(result.confidence).toBe("high");
  });

  it("detects native Android", () => {
    const result = detectProjectType(["gradlew", "app/build.gradle", "app/src/"]);
    expect(result.projectType).toBe("android");
    expect(result.confidence).toBe("high");
  });

  it("detects native iOS", () => {
    const result = detectProjectType(["MyApp.xcodeproj/project.pbxproj", "MyApp/AppDelegate.swift"]);
    expect(result.projectType).toBe("ios");
    expect(result.confidence).toBe("high");
  });

  it("detects Unity", () => {
    const result = detectProjectType(["Assets/Scripts/Player.cs", "ProjectSettings/ProjectSettings.asset"]);
    expect(result.projectType).toBe("unity");
    expect(result.confidence).toBe("high");
  });

  it("detects KMM", () => {
    const result = detectProjectType(["shared/src/commonMain/kotlin/App.kt", "androidApp/src/main/", "iosApp/iosApp/"]);
    expect(result.projectType).toBe("kmm");
    expect(result.confidence).toBe("high");
  });

  it("detects Snap", () => {
    const result = detectProjectType(["snapcraft.yaml", "src/", "README.md"]);
    expect(result.projectType).toBe("snap");
    expect(result.confidence).toBe("high");
  });

  it("detects .NET MAUI", () => {
    const result = detectProjectType(["MyApp/MyApp.csproj", "Platforms/Android/MainActivity.cs", "Platforms/iOS/AppDelegate.cs"]);
    expect(result.projectType).toBe("dotnet-maui");
    expect(result.confidence).toBe("high");
  });

  it("Flutter beats Android when both indicators are present", () => {
    const result = detectProjectType(["pubspec.yaml", "android/build.gradle", "ios/Runner.xcworkspace"]);
    expect(result.projectType).toBe("flutter");
  });

  it("returns unknown for unrecognised project", () => {
    const result = detectProjectType(["README.md", "src/main.py", "requirements.txt"]);
    expect(result.projectType).toBe("unknown");
    expect(result.confidence).toBe("low");
  });

  it("includes a suggestedDebugTemplate for flutter", () => {
    const result = detectProjectType(["pubspec.yaml"]);
    expect(result.suggestedDebugTemplate).toBe("flutter-android-debug");
  });

  it("returns null suggestedDebugTemplate for ios", () => {
    const result = detectProjectType(["MyApp.xcodeproj/"]);
    expect(result.suggestedDebugTemplate).toBeNull();
  });

  it("ignores pubspec.yaml inside example/ subdirectory", () => {
    const result = detectProjectType([
      "package.json", "metro.config.js", "android/", "ios/",
      "example/pubspec.yaml", "example/lib/main.dart",
    ]);
    expect(result.projectType).toBe("react-native");
    expect(result.confidence).toBe("high");
  });

  it("ignores gradle files inside test/fixtures/ subdirectory", () => {
    const result = detectProjectType([
      "MyApp.xcodeproj/project.pbxproj",
      "test/fixtures/android-project/build.gradle",
    ]);
    expect(result.projectType).toBe("ios");
    expect(result.confidence).toBe("high");
  });



});