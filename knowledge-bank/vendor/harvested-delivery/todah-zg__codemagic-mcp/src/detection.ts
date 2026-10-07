export interface DetectionResult {
  projectType: string;
  confidence: "high" | "medium" | "low";
  reasoning: string;
  suggestedDebugTemplate: string | null;
}

const SECONDARY_DIRS = new Set([
  "example", "examples", "test", "tests", "testdata", "__tests__",
  "fixture", "fixtures", "__fixtures__", "playground", "benchmark",
  "benchmarks", "demo", "demos", "sample", "samples", "mock", "mocks",
]);

/**
 * Detect the Codemagic project type from a list of repository file paths.
 * Paths should be relative to the repository root. Include at least two
 * directory levels for best results. For JavaScript projects, provide
 * package.json content to detect React Native vs Ionic from dependencies.
 * @param filePaths - File paths relative to the repository root.
 * @param packageJsonContent - Optional content of package.json as a string.
 * @returns Detected project type with confidence level and reasoning.
 */
export function detectProjectType(
  filePaths: string[],
  packageJsonContent?: string,
): DetectionResult {
  // Normalise: lowercase and forward slashes for consistent matching
  const files = filePaths.map(f => f.toLowerCase().replace(/\\/g, "/"));
  const primaryFiles = files.filter(f => !f.split("/").some(seg => SECONDARY_DIRS.has(seg)));

  const hasPath = (substr: string) => primaryFiles.some(f => f.includes(substr));
  const hasFile = (name: string) => primaryFiles.some(f => f === name || f.endsWith("/" + name));

  // ── Snap ──────────────────────────────────────────────────────────────────
  if (hasFile("snapcraft.yaml") || hasFile("snapcraft.yml")) {
    return {
      projectType: "snap",
      confidence: "high",
      reasoning: "snapcraft.yaml found at repository root",
      suggestedDebugTemplate: null,
    };
  }

  // ── Unity ─────────────────────────────────────────────────────────────────
  if (hasPath("assets/") && hasPath("projectsettings/")) {
    return {
      projectType: "unity",
      confidence: "high",
      reasoning: "Unity project structure detected: Assets/ and ProjectSettings/ directories present",
      suggestedDebugTemplate: null,
    };
  }

  // ── Flutter ───────────────────────────────────────────────────────────────
  if (hasFile("pubspec.yaml")) {
    if (hasPath(".android/") || hasPath(".ios/")) {
      return {
        projectType: "flutter-native",
        confidence: "high",
        reasoning: "pubspec.yaml with .android/ or .ios/ — Flutter add-to-app module pattern",
        suggestedDebugTemplate: "flutter-android-debug",
      };
    }
    return {
      projectType: "flutter",
      confidence: "high",
      reasoning: "pubspec.yaml found",
      suggestedDebugTemplate: "flutter-android-debug",
    };
  }

  // ── .NET MAUI ─────────────────────────────────────────────────────────────
  if (files.some(f => f.endsWith(".csproj")) && hasPath("platforms/")) {
    return {
      projectType: "dotnet-maui",
      confidence: "high",
      reasoning: ".csproj file and Platforms/ directory found — .NET MAUI project",
      suggestedDebugTemplate: null,
    };
  }

  // ── KMM ───────────────────────────────────────────────────────────────────
  if (hasPath("shared/") && (hasPath("androidapp/") || hasPath("iosapp/"))) {
    return {
      projectType: "kmm",
      confidence: "high",
      reasoning: "shared/ module with androidApp/ or iosApp/ — Kotlin Multiplatform Mobile",
      suggestedDebugTemplate: "android-debug",
    };
  }

  // ── JavaScript / Node (React Native, Ionic) ───────────────────────────────
  if (hasFile("package.json")) {

    if (hasPath("capacitor.config.")) {
      return {
        projectType: "ionic-capacitor",
        confidence: "high",
        reasoning: "package.json + capacitor.config file found",
        suggestedDebugTemplate: "android-debug",
      };
    }

    if (hasFile("config.xml")) {
      return {
        projectType: "ionic-cordova",
        confidence: "high",
        reasoning: "package.json + config.xml (Cordova) found",
        suggestedDebugTemplate: "android-debug",
      };
    }

    // Inspect package.json dependencies if provided
    if (packageJsonContent) {
      try {
        const pkg = JSON.parse(packageJsonContent) as {
          dependencies?: Record<string, string>;
          devDependencies?: Record<string, string>;
        };
        const deps = { ...pkg.dependencies, ...pkg.devDependencies };
        if (deps["react-native"] || deps["expo"] || deps["@react-native-community/cli"]) {
          return {
            projectType: "react-native",
            confidence: "high",
            reasoning: "react-native or expo found in package.json dependencies",
            suggestedDebugTemplate: "react-native-android-debug",
          };
        }
      } catch {
        // malformed package.json — fall through to structure-based detection
      }
    }

    if (hasFile("metro.config.js") || hasFile("metro.config.ts")) {
      return {
        projectType: "react-native",
        confidence: "high",
        reasoning: "metro.config.js found — React Native bundler configuration",
        suggestedDebugTemplate: "react-native-android-debug",
      };
    }

    if (hasFile("app.json") || hasFile("app.config.js") || hasFile("app.config.ts")) {
      return {
        projectType: "react-native",
        confidence: "medium",
        reasoning: "Expo configuration file found alongside package.json",
        suggestedDebugTemplate: "react-native-android-debug",
      };
    }

    return {
      projectType: "react-native",
      confidence: "low",
      reasoning: "package.json found but project type unclear. Provide package.json content for accurate detection.",
      suggestedDebugTemplate: "react-native-android-debug",
    };
  }

  // ── Native iOS ────────────────────────────────────────────────────────────
  if (hasPath(".xcodeproj") || hasPath(".xcworkspace")) {
    return {
      projectType: "ios",
      confidence: "high",
      reasoning: "Xcode project or workspace found without other framework indicators",
      suggestedDebugTemplate: null,
    };
  }

  // ── Native Android ────────────────────────────────────────────────────────
  if (hasFile("build.gradle") || hasFile("build.gradle.kts") || hasFile("gradlew")) {
    return {
      projectType: "android",
      confidence: "high",
      reasoning: "Gradle build files found without other framework indicators",
      suggestedDebugTemplate: "android-debug",
    };
  }

  return {
    projectType: "unknown",
    confidence: "low",
    reasoning: "Could not determine project type. Provide more file paths or package.json content.",
    suggestedDebugTemplate: null,
  };
}