// codemagic.yaml starter templates — one per project type.
//
// Design conventions:
//   - Build and signing only. No publishing sections (handled via ASC/Google Play tools).
//   - BUILD_NUMBER and VERSION_NAME are injected as variables at trigger time.
//     The AI agent should determine these values via list_asc_builds / list_google_play_tracks
//     before calling trigger_build, then pass them in the `variables` parameter.
//   - Every line that the user must change is annotated with "# Replace with..."
//   - Placeholder package names / bundle IDs use com.example.myapp consistently.
//   - Android-only workflows use linux_x2 (cheaper, no Mac needed).
//   - iOS or combined workflows use mac_mini_m2.
//   - Unity workflows use mac_mini_m2 (builds both Android and iOS targets).
//   - The `publishing.scripts` block in Unity templates is for license deactivation,
//     not app distribution — it runs post-build regardless of outcome.

export const TEMPLATES: Record<string, string> = {

  // ─── Native Android ──────────────────────────────────────────────────────────

  android: `# Native Android — build and sign an AAB for Google Play distribution.
#
# Before triggering:
#   1. Add a keystore in Codemagic → Code signing → Android keystores.
#      The reference name below must match what you entered there.
#   2. Determine the next BUILD_NUMBER and VERSION_NAME using the google-play CLI
#      (list_google_play_tracks), then pass them as variables to trigger_build.
workflows:
  android-workflow:
    name: Native Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Set Android SDK location
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/local.properties"
      - name: Build Android release
        script: |
          ./gradlew bundleRelease \\
            -PversionCode=$BUILD_NUMBER \\
            -PversionName=$VERSION_NAME
    artifacts:
      - app/build/outputs/**/*.aab
      - app/build/outputs/**/*.apk`,

  // ─── Native iOS ──────────────────────────────────────────────────────────────

  ios: `# Native iOS — build and sign an IPA for App Store distribution.
#
# Before triggering:
#   1. Add a distribution certificate and provisioning profile in
#      Codemagic → Code signing → iOS certificates.
#   2. Determine the next BUILD_NUMBER and VERSION_NAME using the asc CLI
#      (list_asc_builds), then pass them as variables to trigger_build.
workflows:
  ios-workflow:
    name: Native iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      vars:
        XCODE_WORKSPACE: MyApp.xcworkspace       # Replace with your .xcworkspace filename
        XCODE_SCHEME: MyApp                      # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER              # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME              # Injected via trigger_build variables
    scripts:
      - name: Install CocoaPods dependencies
        script: |
          pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --workspace "$CM_BUILD_DIR/$XCODE_WORKSPACE" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM`,

  // ─── Flutter ─────────────────────────────────────────────────────────────────

  flutter: `# Flutter — separate workflows for Android AAB and iOS IPA.
# Trigger them independently with the appropriate BUILD_NUMBER/VERSION_NAME.
#
# Before triggering android:
#   1. Add a keystore in Codemagic → Code signing → Android keystores.
#   2. Determine build number via list_google_play_tracks.
#
# Before triggering ios:
#   1. Add signing identity in Codemagic → Code signing → iOS certificates.
#   2. Determine build number via list_asc_builds.
workflows:
  flutter-android:
    name: Flutter Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      flutter: stable
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Get Flutter packages
        script: |
          flutter pub get
      - name: Build Android release
        script: |
          flutter build appbundle --release \\
            --build-number=$BUILD_NUMBER \\
            --build-name=$VERSION_NAME
    artifacts:
      - build/**/outputs/**/*.aab

  flutter-ios:
    name: Flutter iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      flutter: stable
      vars:
        BUILD_NUMBER: $BUILD_NUMBER    # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME    # Injected via trigger_build variables
    scripts:
      - name: Get Flutter packages
        script: |
          flutter pub get
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Build IPA
        script: |
          flutter build ipa --release \\
            --build-number=$BUILD_NUMBER \\
            --build-name=$VERSION_NAME \\
            --export-options-plist=/Users/builder/export_options.plist
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM`,

  // ─── Flutter Native Module ────────────────────────────────────────────────────

  "flutter-native": `# Native app with embedded Flutter module.
# Use this when you have a native Android or iOS host app that integrates
# a Flutter module as a library (add-to-app pattern).
#
# Adjust FLUTTER_MODULE_DIR and HOST_APP_DIR to match your repo layout.
workflows:
  flutter-native-android:
    name: Native Android with Flutter Module
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      flutter: stable
      vars:
        FLUTTER_MODULE_DIR: my_flutter_module    # Replace with your Flutter module directory
        HOST_APP_DIR: my_host_app                # Replace with your native Android app directory
        PACKAGE_NAME: com.example.myapp          # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER              # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME              # Injected via trigger_build variables
    scripts:
      - name: Set Android SDK location
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/$HOST_APP_DIR/local.properties"
      - name: Get Flutter packages
        script: |
          cd $CM_BUILD_DIR/$FLUTTER_MODULE_DIR && flutter pub get
      - name: Build Flutter AAR
        script: |
          cd $CM_BUILD_DIR/$FLUTTER_MODULE_DIR && flutter build aar
      - name: Build host app
        script: |
          cd $CM_BUILD_DIR/$HOST_APP_DIR
          ./gradlew bundleRelease \\
            -PversionCode=$BUILD_NUMBER \\
            -PversionName=$VERSION_NAME
    artifacts:
      - "**/*.aab"

  flutter-native-ios:
    name: Native iOS with Flutter Module
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      flutter: stable
      vars:
        FLUTTER_MODULE_DIR: my_flutter_module    # Replace with your Flutter module directory
        HOST_APP_DIR: my_host_app                # Replace with your native iOS app directory
        XCODE_PROJECT: MyApp.xcodeproj           # Replace with your Xcode project filename
        XCODE_SCHEME: MyApp                      # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER              # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME              # Injected via trigger_build variables
    scripts:
      - name: Get Flutter packages and build iOS framework
        script: |
          cd $CM_BUILD_DIR/$FLUTTER_MODULE_DIR
          flutter pub get
          flutter build ios-framework \\
            --output=$CM_BUILD_DIR/$HOST_APP_DIR/Flutter
      - name: Install CocoaPods dependencies
        script: |
          cd $CM_BUILD_DIR/$HOST_APP_DIR && pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/$HOST_APP_DIR
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --project "$CM_BUILD_DIR/$HOST_APP_DIR/$XCODE_PROJECT" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM`,

  // ─── React Native ─────────────────────────────────────────────────────────────

  "react-native": `# React Native — separate workflows for Android AAB and iOS IPA.
# This template assumes Expo. If you are not using Expo, remove the
# 'Run Expo Prebuild' steps from both workflows.
workflows:
  react-native-android:
    name: React Native Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      node: latest
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Set Android SDK location
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/android/local.properties"
      - name: Install npm dependencies
        script: |
          npm install
      - name: Run Expo Prebuild
        script: |
          npx expo prebuild
      - name: Build Android release
        script: |
          cd android
          ./gradlew bundleRelease \\
            -PversionCode=$BUILD_NUMBER \\
            -PversionName=$VERSION_NAME
    artifacts:
      - android/app/build/outputs/**/*.aab

  react-native-ios:
    name: React Native iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      node: latest
      vars:
        XCODE_WORKSPACE: MyApp.xcworkspace    # Replace with your .xcworkspace filename
        XCODE_SCHEME: MyApp                   # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER           # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME           # Injected via trigger_build variables
    scripts:
      - name: Install npm dependencies
        script: |
          npm install
      - name: Run Expo Prebuild
        script: |
          npx expo prebuild
      - name: Install CocoaPods dependencies
        script: |
          cd ios && pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/ios
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --workspace "$CM_BUILD_DIR/ios/$XCODE_WORKSPACE" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM`,

  // ─── Ionic Capacitor ─────────────────────────────────────────────────────────

  "ionic-capacitor": `# Ionic Capacitor — separate workflows for Android AAB and iOS IPA.
workflows:
  ionic-capacitor-android:
    name: Ionic Capacitor Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      node: latest
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Set Android SDK location
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/android/local.properties"
      - name: Install npm dependencies
        script: |
          npm install
      - name: Build web assets
        script: |
          npm run build
      - name: Sync Capacitor
        script: |
          npx cap sync
      - name: Build Android release
        script: |
          cd android
          ./gradlew bundleRelease \\
            -PversionCode=$BUILD_NUMBER \\
            -PversionName=$VERSION_NAME
    artifacts:
      - android/app/build/outputs/**/*.aab

  ionic-capacitor-ios:
    name: Ionic Capacitor iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      node: latest
      vars:
        XCODE_WORKSPACE: MyApp.xcworkspace    # Replace with your .xcworkspace filename
        XCODE_SCHEME: MyApp                   # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER           # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME           # Injected via trigger_build variables
    scripts:
      - name: Install npm dependencies
        script: |
          npm install
      - name: Build web assets
        script: |
          npm run build
      - name: Sync Capacitor
        script: |
          npx cap sync
      - name: Install CocoaPods dependencies
        script: |
          cd ios && pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/ios
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --workspace "$CM_BUILD_DIR/ios/$XCODE_WORKSPACE" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log`,

  // ─── Ionic Cordova ────────────────────────────────────────────────────────────

  "ionic-cordova": `# Ionic Cordova — separate workflows for Android APK and iOS IPA.
# Cordova builds APKs rather than AABs. Google Play accepts both, but AABs
# are preferred for new apps. Check the Codemagic Cordova docs if you need AAB.
workflows:
  ionic-cordova-android:
    name: Ionic Cordova Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      node: latest
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Install npm dependencies
        script: |
          npm install
      - name: Install Cordova
        script: |
          npm install -g cordova
      - name: Add Android platform
        script: |
          ionic cordova platform remove android --nosave
          ionic cordova platform add android \\
            --confirm \\
            --no-interactive \\
            --noresources
      - name: Build Android release
        script: |
          ionic cordova build android \\
            --release \\
            --no-interactive \\
            --prod \\
            --device
    artifacts:
      - platforms/android/app/build/outputs/**/*.apk

  ionic-cordova-ios:
    name: Ionic Cordova iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      node: latest
      vars:
        XCODE_WORKSPACE: MyApp.xcworkspace    # Replace with your .xcworkspace filename
        XCODE_SCHEME: MyApp                   # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER           # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME           # Injected via trigger_build variables
    scripts:
      - name: Install npm dependencies
        script: |
          npm install
      - name: Install Cordova
        script: |
          npm install -g cordova
      - name: Add iOS platform
        script: |
          ionic cordova platform add ios \\
            --confirm \\
            --no-interactive
      - name: Install CocoaPods dependencies
        script: |
          cd platforms/ios && pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/platforms/ios
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --workspace "$CM_BUILD_DIR/platforms/ios/$XCODE_WORKSPACE" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log`,

  // ─── Kotlin Multiplatform Mobile ─────────────────────────────────────────────

  kmm: `# Kotlin Multiplatform Mobile (KMM) — Android AAB and iOS IPA.
# Default project structure assumes androidApp/ and iosApp/ subdirectories.
# Adjust XCODE_WORKSPACE and gradlew task if your layout differs.
workflows:
  kmm-android:
    name: KMM Android
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      android_signing:
        - keystore_reference
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Set Android SDK location
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/local.properties"
      - name: Build Android release
        script: |
          ./gradlew androidApp:bundleRelease \\
            -PversionCode=$BUILD_NUMBER \\
            -PversionName=$VERSION_NAME
    artifacts:
      - androidApp/build/outputs/**/*.aab

  kmm-ios:
    name: KMM iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp           # Replace with your bundle ID
      vars:
        XCODE_WORKSPACE: iosApp/MyApp.xcworkspace       # Replace with your .xcworkspace path
        XCODE_SCHEME: iosApp                            # Replace with your Xcode scheme name
        BUILD_NUMBER: $BUILD_NUMBER                     # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME                     # Injected via trigger_build variables
    scripts:
      - name: Install CocoaPods dependencies
        script: |
          cd iosApp && pod install
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/iosApp
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --workspace "$CM_BUILD_DIR/$XCODE_WORKSPACE" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
      - $HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM`,

  // ─── Linux Snap ──────────────────────────────────────────────────────────────

  snap: `# Linux Snap Package — build a snap using Snapcraft.
# The snapcraft.yaml in your repository defines the snap configuration.
# Set SNAPCRAFT_CREDENTIALS in a Codemagic variable group for publishing to the Snap Store.
workflows:
  snap-build:
    name: Snap Package
    max_build_duration: 120
    instance_type: linux_x2
    environment:
      vars:
        SNAP_NAME: my-app    # Replace with your snap name (used for the output filename)
        SNAPCRAFT_BUILD_ENVIRONMENT: host
    scripts:
      - name: Build snap
        script: |
          snapcraft snap --output $SNAP_NAME.snap
    artifacts:
      - "**/*.snap"`,

  // ─── Unity (Android + iOS) ───────────────────────────────────────────────────

  unity: `# Unity — build Android AAB and iOS IPA from a Unity project.
#
# Requirements:
#   - A variable group named 'unity_credentials' containing:
#       UNITY_SERIAL, UNITY_EMAIL, UNITY_PASSWORD
#   - A BuildScript.cs in your Unity project with static BuildAndroid() and BuildIos() methods
#   - Code signing set up for both platforms in Codemagic
#
# The publishing.scripts block runs post-build to deactivate the Unity license.
# This is required cleanup — it is not related to app store publishing.
workflows:
  unity-android:
    name: Unity Android
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      android_signing:
        - keystore_reference
      groups:
        - unity_credentials
      vars:
        UNITY_BIN: $UNITY_HOME/Contents/MacOS/Unity
        PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        BUILD_NUMBER: $BUILD_NUMBER        # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME        # Injected via trigger_build variables
    scripts:
      - name: Activate Unity license
        script: |
          $UNITY_BIN -batchmode -quit -logFile \\
            -serial \${UNITY_SERIAL} \\
            -username \${UNITY_EMAIL} \\
            -password \${UNITY_PASSWORD}
      - name: Build Android
        script: |
          $UNITY_BIN -batchmode \\
            -quit \\
            -logFile \\
            -projectPath . \\
            -executeMethod BuildScript.BuildAndroid \\
            -nographics
    artifacts:
      - android/*.aab
      - android/*.apk
    publishing:
      scripts:
        - name: Deactivate Unity license
          script: |
            $UNITY_BIN -batchmode -quit -logFile \\
              -returnlicense \\
              -username \${UNITY_EMAIL} \\
              -password \${UNITY_PASSWORD}

  unity-ios:
    name: Unity iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp        # Replace with your bundle ID
      groups:
        - unity_credentials
      vars:
        UNITY_BIN: $UNITY_HOME/Contents/MacOS/Unity
        XCODE_PROJECT: ios/Unity-iPhone.xcodeproj   # Default Unity Xcode project path
        XCODE_SCHEME: Unity-iPhone                  # Default Unity Xcode scheme
        BUILD_NUMBER: $BUILD_NUMBER                 # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME                 # Injected via trigger_build variables
    scripts:
      - name: Activate Unity license
        script: |
          $UNITY_BIN -batchmode -quit -logFile \\
            -serial \${UNITY_SERIAL} \\
            -username \${UNITY_EMAIL} \\
            -password \${UNITY_PASSWORD}
      - name: Build iOS (generates Xcode project)
        script: |
          $UNITY_BIN -batchmode \\
            -quit \\
            -logFile \\
            -projectPath . \\
            -executeMethod BuildScript.BuildIos \\
            -nographics
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Set build number
        script: |
          cd $CM_BUILD_DIR/ios
          agvtool new-version -all $BUILD_NUMBER
      - name: Build IPA
        script: |
          xcode-project build-ipa \\
            --project "$CM_BUILD_DIR/$XCODE_PROJECT" \\
            --scheme "$XCODE_SCHEME"
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
    publishing:
      scripts:
        - name: Deactivate Unity license
          script: |
            $UNITY_BIN -batchmode -quit -logFile \\
              -returnlicense \\
              -username \${UNITY_EMAIL} \\
              -password \${UNITY_PASSWORD}`,

  // ─── Unity Oculus VR ─────────────────────────────────────────────────────────

  "unity-oculus": `# Unity Oculus VR — build and publish an APK for Oculus Quest.
#
# Requirements:
#   - A variable group named 'unity_credentials':
#       UNITY_SERIAL, UNITY_EMAIL, UNITY_PASSWORD
#   - A variable group named 'oculus_credentials':
#       OCULUS_APP_ID, OCULUS_APP_SECRET
#   - A BuildScript.cs with a static BuildAndroid() method
#   - An Android keystore set up in Codemagic → Code signing
#
# The publishing.scripts block deactivates the Unity license and uploads to Oculus.
# The Oculus Platform Utility (ovr-platform-util) is downloaded at publish time.
workflows:
  unity-oculus-workflow:
    name: Unity Oculus VR
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      android_signing:
        - keystore_reference
      groups:
        - unity_credentials
        - oculus_credentials
      vars:
        UNITY_BIN: $UNITY_HOME/Contents/MacOS/Unity
        OCULUS_RELEASE_CHANNEL: ALPHA    # Replace with target channel: ALPHA, BETA, RC, or STORE
        BUILD_NUMBER: $BUILD_NUMBER      # Injected via trigger_build variables
    scripts:
      - name: Activate Unity license
        script: |
          $UNITY_BIN -batchmode -quit -logFile \\
            -serial \${UNITY_SERIAL} \\
            -username \${UNITY_EMAIL} \\
            -password \${UNITY_PASSWORD}
      - name: Build Android APK
        script: |
          $UNITY_BIN -batchmode \\
            -quit \\
            -logFile \\
            -projectPath . \\
            -executeMethod BuildScript.BuildAndroid \\
            -nographics \\
            -buildTarget Android
    artifacts:
      - android/*.apk
    publishing:
      scripts:
        - name: Deactivate Unity license
          script: |
            $UNITY_BIN -batchmode -quit -logFile \\
              -returnlicense \\
              -username \${UNITY_EMAIL} \\
              -password \${UNITY_PASSWORD}
        - name: Install Oculus Platform Utility
          script: |
            wget -O ovr-platform-util \\
              "https://www.oculus.com/download_app/?id=1462426033810370&access_token=OC|1462426033810370|"
            chmod +x ./ovr-platform-util
        - name: Upload to Oculus
          script: |
            ./ovr-platform-util upload-quest-build \\
              --app_id \${OCULUS_APP_ID} \\
              --app_secret \${OCULUS_APP_SECRET} \\
              --apk android/android.apk \\
              --channel $OCULUS_RELEASE_CHANNEL`,

  // ─── .NET MAUI ───────────────────────────────────────────────────────────────

  "dotnet-maui": `# .NET MAUI — build iOS IPA and Android AAB.
# .NET SDK and MAUI workloads are installed from the Microsoft installer at build time.
# Replace PROJECT_PATH with the path to your .csproj file.
workflows:
  maui-ios:
    name: MAUI iOS
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp    # Replace with your bundle ID
      vars:
        DOTNET_PATH: $CM_BUILD_DIR/dotnet
        DOTNET: $CM_BUILD_DIR/dotnet/dotnet
        PROJECT_PATH: src/MyApp/MyApp.csproj    # Replace with your .csproj path
        BUILD_NUMBER: $BUILD_NUMBER             # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME             # Injected via trigger_build variables
    scripts:
      - name: Install .NET SDK
        script: |
          wget https://dot.net/v1/dotnet-install.sh
          chmod +x dotnet-install.sh
          ./dotnet-install.sh --install-dir $DOTNET_PATH
      - name: Install MAUI workloads
        script: |
          $DOTNET nuget locals all --clear
          $DOTNET workload install ios maui \\
            --source https://aka.ms/dotnet/nuget/index.json \\
            --source https://api.nuget.org/v3/index.json
      - name: Set up provisioning profiles
        script: xcode-project use-profiles
      - name: Build iOS IPA
        script: |
          CERT_NAME=$(keychain list-certificates | jq -r '.[0].common_name')
          PROFILE_NAME=$(find ~/Library/MobileDevice/Provisioning\\ Profiles -name "*.mobileprovision" | head -1 | xargs -I{} /usr/libexec/PlistBuddy -c "print :Name" /dev/stdin <<< $(security cms -D -i {}))
          $DOTNET publish $PROJECT_PATH \\
            -f net8.0-ios \\
            -c Release \\
            -p:BuildIpa=True \\
            -p:ApplicationDisplayVersion="$VERSION_NAME" \\
            -p:ApplicationVersion=$BUILD_NUMBER \\
            -p:RuntimeIdentifier=ios-arm64 \\
            -p:CodesignKey="$CERT_NAME" \\
            -p:CodesignProvision="$PROFILE_NAME" \\
            -o artifacts
    artifacts:
      - artifacts/*.ipa

  maui-android:
    name: MAUI Android
    max_build_duration: 120
    instance_type: mac_mini_m2
    environment:
      android_signing:
        - keystore_reference
      vars:
        DOTNET_PATH: $CM_BUILD_DIR/dotnet
        DOTNET: $CM_BUILD_DIR/dotnet/dotnet
        PACKAGE_NAME: com.example.myapp         # Replace with your application ID
        PROJECT_PATH: src/MyApp/MyApp.csproj    # Replace with your .csproj path
        BUILD_NUMBER: $BUILD_NUMBER             # Injected via trigger_build variables
        VERSION_NAME: $VERSION_NAME             # Injected via trigger_build variables
    scripts:
      - name: Install .NET SDK
        script: |
          wget https://dot.net/v1/dotnet-install.sh
          chmod +x dotnet-install.sh
          ./dotnet-install.sh --install-dir $DOTNET_PATH
      - name: Install MAUI workloads
        script: |
          $DOTNET nuget locals all --clear
          $DOTNET workload install android maui \\
            --source https://aka.ms/dotnet/nuget/index.json \\
            --source https://api.nuget.org/v3/index.json
      - name: Build Android AAB
        script: |
          $DOTNET publish $PROJECT_PATH \\
            -f net8.0-android \\
            -c Release \\
            -p:AndroidKeyStore=True \\
            -p:AndroidSigningKeyStore=$CM_KEYSTORE_PATH \\
            -p:AndroidSigningKeyAlias=$CM_KEY_ALIAS \\
            -p:AndroidSigningKeyPass=$CM_KEY_PASSWORD \\
            -p:AndroidSigningStorePass=$CM_KEYSTORE_PASSWORD \\
            -p:ApplicationVersion=$BUILD_NUMBER \\
            -p:ApplicationDisplayVersion="$VERSION_NAME" \\
            -o artifacts
    artifacts:
      - artifacts/*Signed.aab`,

      // ─── Onboarding / Debug builds ───────────────────────────────────────────────

      "android-debug": `# Android debug build — for onboarding and initial setup only.
    # No signing or instance_type override required — runs on the free tier.
    # Once this build succeeds, switch to the 'android' template for release builds.
    workflows:
      android-debug:
        name: Android Debug
        max_build_duration: 60
        environment:
          vars:
            PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        scripts:
          - name: Set Android SDK location
            script: |
              echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/local.properties"
          - name: Build Android debug
            script: |
              ./gradlew assembleDebug
        artifacts:
          - app/build/outputs/**/*.apk`,
    
      "flutter-android-debug": `# Flutter Android debug build — for onboarding and initial setup only.
    # No signing or instance_type override required — runs on the free tier.
    # Once this build succeeds, switch to the 'flutter' template for release builds.
    workflows:
      flutter-android-debug:
        name: Flutter Android Debug
        max_build_duration: 60
        environment:
          flutter: stable
          vars:
            PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        scripts:
          - name: Get Flutter packages
            script: |
              flutter pub get
          - name: Build Android debug
            script: |
              flutter build apk --debug
        artifacts:
          - build/**/outputs/**/*.apk`,
    
      "react-native-android-debug": `# React Native Android debug build — for onboarding and initial setup only.
    # No signing or instance_type override required — runs on the free tier.
    # Assumes Expo — remove the 'Run Expo Prebuild' step if not using Expo.
    # Once this build succeeds, switch to the 'react-native' template for release builds.
    workflows:
      react-native-android-debug:
        name: React Native Android Debug
        max_build_duration: 60
        environment:
          node: latest
          vars:
            PACKAGE_NAME: com.example.myapp    # Replace with your application ID
        scripts:
          - name: Set Android SDK location
            script: |
              echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/android/local.properties"
          - name: Install npm dependencies
            script: |
              npm install
          - name: Run Expo Prebuild
            script: |
              npx expo prebuild
          - name: Build Android debug
            script: |
              cd android
              ./gradlew assembleDebug
        artifacts:
          - android/app/build/outputs/**/*.apk`,

  // ─── Screenshot capture ──────────────────────────────────────────────────────

  "ios-screenshots": `# iOS Screenshots — capture App Store screenshots using Maestro on an iOS simulator.
# Produces IPHONE_65 screenshots (1284x2778) by default; change SIMULATOR for other sizes.
#
# Before triggering:
#   1. Replace BUNDLE_ID with your app's bundle identifier.
#   2. Replace the "Build app for simulator" script with your framework's command:
#        Flutter:  flutter build ios --simulator --debug
#        RN:       npx react-native build-ios --mode Debug
#        Xcode:    xcodebuild -scheme SCHEME -destination "platform=iOS Simulator,name=$SIMULATOR" -configuration Debug build
#   3. Replace the app path in "Install app" with your framework's output path:
#        Flutter:  find build/ios/iphonesimulator -name "*.app" | head -1
#        Xcode:    build/Debug-iphonesimulator/MyApp.app
#   4. Create a Maestro flow at .maestro/screenshots.yaml. Example:
#        appId: com.example.myapp
#        ---
#        - launchApp
#        - takeScreenshot: "screenshots/en-US/IPHONE_65/01_home"
#        - tapOn: "Get Started"
#        - takeScreenshot: "screenshots/en-US/IPHONE_65/02_onboarding"
#
# Screenshot artifacts are exposed individually — pass their URLs to upload_ios_screenshots.
workflows:
  ios-screenshots:
    name: iOS Screenshots
    max_build_duration: 60
    instance_type: mac_mini_m2
    environment:
      xcode: latest
      vars:
        BUNDLE_ID: com.example.myapp    # Replace with your bundle ID
        SIMULATOR: iPhone 15 Pro Max    # Produces IPHONE_65 screenshots (1284x2778)
    scripts:
      - name: Install Maestro
        script: |
          curl -Ls "https://get.maestro.mobile.dev" | bash
          echo "PATH=$HOME/.maestro/bin:$PATH" >> $CM_ENV
      - name: Build app for simulator
        script: |
          flutter build ios --simulator --debug    # Replace with your build command
      - name: Boot simulator
        script: |
          xcrun simctl boot "$SIMULATOR" || true
          open -a Simulator
          xcrun simctl bootstatus "$SIMULATOR" -b
      - name: Install app on simulator
        script: |
          APP_PATH=$(find build/ios/iphonesimulator -name "*.app" | head -1)    # Replace path if not Flutter
          xcrun simctl install "$SIMULATOR" "$APP_PATH"
      - name: Capture screenshots
        script: |
          mkdir -p screenshots
          maestro test .maestro/screenshots.yaml
    artifacts:
      - screenshots/**/*.png
      - screenshots/**/*.jpg`,

  "android-screenshots": `# Android Screenshots — capture Google Play screenshots using Maestro on an Android emulator.
# Runs on a Linux instance where Android emulators are available.
#
# Before triggering:
#   1. Replace PACKAGE_NAME with your app's package name.
#   2. Replace the "Build debug APK" script with your framework's command:
#        Flutter:  flutter build apk --debug
#        RN:       npx react-native build-android --mode debug
#        Native:   ./gradlew assembleDebug
#   3. Replace the APK path in "Install app" if not using the default Gradle output.
#   4. Create a Maestro flow at .maestro/screenshots.yaml. Example:
#        appId: com.example.myapp
#        ---
#        - launchApp
#        - takeScreenshot: "screenshots/en-US/phoneScreenshots/01_home"
#        - tapOn: "Get Started"
#        - takeScreenshot: "screenshots/en-US/phoneScreenshots/02_onboarding"
#
# Screenshot artifacts are exposed individually — pass their URLs to upload_android_screenshots.
workflows:
  android-screenshots:
    name: Android Screenshots
    max_build_duration: 60
    instance_type: linux_x2
    environment:
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your package name
        AVD_NAME: codemagic_screenshots
        SYSTEM_IMAGE: system-images;android-33;google_apis;x86_64
    scripts:
      - name: Install Maestro
        script: |
          curl -Ls "https://get.maestro.mobile.dev" | bash
          echo "PATH=$HOME/.maestro/bin:$PATH" >> $CM_ENV
      - name: Create and boot Android emulator
        script: |
          sdkmanager --install "$SYSTEM_IMAGE"
          echo "no" | avdmanager create avd -n "$AVD_NAME" -k "$SYSTEM_IMAGE" --force
          $ANDROID_SDK_ROOT/emulator/emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim &
          adb wait-for-device shell 'while [[ -z $(getprop sys.boot_completed) ]]; do sleep 3; done'
      - name: Build debug APK
        script: |
          echo "sdk.dir=$ANDROID_SDK_ROOT" > "$CM_BUILD_DIR/local.properties"
          ./gradlew assembleDebug    # Replace with your build command
      - name: Install app on emulator
        script: |
          APK_PATH=$(find . -name "*.apk" -not -path "*/test*" | head -1)    # Replace path if not Gradle default
          adb install -r "$APK_PATH"
      - name: Capture screenshots
        script: |
          mkdir -p screenshots
          maestro test .maestro/screenshots.yaml
    artifacts:
      - screenshots/**/*.png
      - screenshots/**/*.jpg`,

  "flutter-screenshots": `# Flutter Screenshots — capture store screenshots using Flutter golden tests.
# No simulator or emulator required — renders widgets at exact store dimensions.
# Works on any instance type; use linux_x2 for cost efficiency.
#
# Before triggering:
#   1. Replace PACKAGE_NAME with your app's package name.
#   2. Write golden tests that render your screens at store dimensions. Example:
#
#      // test/screenshots/store_screenshots_test.dart
#      void main() {
#        testWidgets('home screen - IPHONE_65', (tester) async {
#          await tester.binding.setSurfaceSize(const Size(1284, 2778));
#          await tester.pumpWidget(const MyApp());
#          await tester.pumpAndSettle();
#          await expectLater(
#            find.byType(MyApp),
#            matchesGoldenFile('goldens/en-US/IPHONE_65/01_home.png'),
#          );
#        });
#        testWidgets('home screen - phoneScreenshots', (tester) async {
#          await tester.binding.setSurfaceSize(const Size(1080, 1920));
#          await tester.pumpWidget(const MyApp());
#          await tester.pumpAndSettle();
#          await expectLater(
#            find.byType(MyApp),
#            matchesGoldenFile('goldens/en-US/phoneScreenshots/01_home.png'),
#          );
#        });
#      }
#
# Screenshot artifacts are exposed individually — pass their URLs to
# upload_ios_screenshots (IPHONE_65 set) and upload_android_screenshots (phoneScreenshots set).
workflows:
  flutter-screenshots:
    name: Flutter Screenshots
    max_build_duration: 30
    instance_type: linux_x2
    environment:
      flutter: stable
      vars:
        PACKAGE_NAME: com.example.myapp    # Replace with your package name
    scripts:
      - name: Get Flutter packages
        script: |
          flutter pub get
      - name: Generate screenshots via golden tests
        script: |
          flutter test test/screenshots/ --update-goldens
    artifacts:
      - test/screenshots/goldens/**/*.png`,
};

/**
 * Get a starter codemagic.yaml template for a given project type.
 * Templates cover build and signing only — publishing is handled via ASC/Google Play tools.
 * BUILD_NUMBER and VERSION_NAME must be injected via trigger_build variables;
 * determine them first using list_asc_builds or list_google_play_tracks.
 * @param projectType - One of the supported project types (see listYamlTemplateTypes).
 * @returns The yaml template string, or null if the project type is not recognised.
 */
export function getYamlTemplate(projectType: string): string | null {
  return TEMPLATES[projectType] ?? null;
}

/**
 * List all supported project type keys for yaml templates.
 * @returns Array of project type strings, e.g. ["android", "ios", "flutter", ...].
 */
export function listYamlTemplateTypes(): string[] {
  return Object.keys(TEMPLATES);
}
