import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const ONBOARDING_GUIDE = `
# Codemagic Onboarding — Zero to First Build

Goal: get an Android debug build passing to prove the project compiles on Codemagic.
Signing, release builds, and store publishing come after this succeeds.

1. ADD THE APPLICATION
   Call add_application with the repository URL.
   Note the app_id returned.

2. DETECT THE PROJECT TYPE
   If you have a listing of the repository's files, call detect_project_type
   with that list. It returns a debugTemplate field — use that value as the
   type in step 3.
   If you do not have the file listing, skip this step and pick the type manually.

3. GET A DEBUG TEMPLATE
   Call get_yaml_template with the matching debug project type:
     android-debug, flutter-android-debug, or react-native-android-debug.
   Replace PACKAGE_NAME with the actual application ID.
   NOTE: Android templates default to linux_x2. Personal accounts (no team) cannot
   use linux_x2 — replace it with mac_mini_m2 before validating or triggering.

4. VALIDATE THE YAML
   Call validate_codemagic_yaml with the edited yaml.
   Fix any errors before proceeding.

5. TRIGGER THE FIRST BUILD
   Call trigger_build with:
     app_id    — from step 1
     workflow_id — the workflow name inside the yaml (e.g. "android-debug")
     branch    — the default branch (main or master)
     yaml_content — the validated yaml from step 2

6. WAIT FOR THE RESULT
   Call wait_for_build with the build ID.
   A green build means the project compiles on Codemagic.

7. CONFIGURE WEBHOOKS (optional)
   Call get_webhook_url with the app ID.
   Add the returned URL to the repository webhook settings in GitHub/GitLab/Bitbucket
   to enable automatic builds on push.

Next steps: once the debug build passes, use the android_release or ios_release prompt.
`.trim();

const ANDROID_RELEASE_GUIDE = `
# Android Release — Signed AAB to Google Play

Prerequisites:
  - Android keystore uploaded in Codemagic → Code signing → Android keystores
    (the reference name in the template is "keystore_reference")
  - GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS set in the environment

1. DETERMINE THE NEXT BUILD NUMBER
   Call get_latest_build_number with the package name.
   Increment the result by 1 — this is BUILD_NUMBER.
   Decide VERSION_NAME (e.g. "1.2.0").

2. GET THE RELEASE TEMPLATE
   Call get_yaml_template with the matching project type:
     android, flutter, react-native, ionic-capacitor, ionic-cordova, kmm, etc.
   Replace PACKAGE_NAME with the actual application ID.

3. VALIDATE THE YAML
   Call validate_codemagic_yaml with the edited yaml.

4. TRIGGER THE BUILD
   Call trigger_build with:
     app_id, workflow_id, branch
     yaml_content — the validated yaml
     variables    — { "BUILD_NUMBER": "42", "VERSION_NAME": "1.2.0" }

5. WAIT FOR THE BUILD
   Call wait_for_build. Note the AAB artifact URL on success.

6. PUBLISH TO INTERNAL TRACK
   Call upload_to_google_play with:
     aab_url — the AAB artifact URL from step 5
     track   — "internal" (safest starting point)
     release_notes (optional)
   Alternatively, call share_app_internally for an instant QA install link
   with no track or review ceremony before committing to a track.

7. PROMOTE TO PRODUCTION
   Call promote_google_play_release to move the release up the tracks:
     internal → alpha → beta → production
   Promote one track at a time and verify before moving to the next.
   For staged rollout on the target track: set user_fraction (e.g. 0.1 = 10%).
   To expand the rollout: call set_rollout_fraction with a higher fraction.
   To halt a staged rollout: call promote_google_play_release with
     source_track=target_track="production" and release_status="halted".
   To resume: same call with release_status="inProgress" and a user_fraction.
`.trim();

const FIRST_PUBLISH_IOS = `
# iOS First Publish — One-Time Setup Checklist

This is the one-time human session before an agent can manage your App Store releases.
Complete every item below, then use the /ios_release workflow prompt for all future releases.

Estimated time: 10–20 minutes (plus Apple review, which can take 24–48 h).

---

STEP 1 — APPLE DEVELOPER PROGRAM
  Enroll at developer.apple.com if you have not already.
  Cost: $99/year. Required to distribute any app outside TestFlight internal testing.

STEP 2 — SIGN AGREEMENTS IN APP STORE CONNECT
  Go to App Store Connect → Business → Agreements.
  Accept the Free Apps Agreement.
  If you sell anything (paid app, in-app purchases): also accept the Paid Apps Agreement
  and complete banking and tax information. The Paid Apps Agreement must be Active
  before you can submit anything.

STEP 3 — CREATE THE APP RECORD
  Go to App Store Connect → My Apps → (+) → New App.
  Fill in:
    Platform: iOS
    Name: your app's display name (can be changed later before release)
    Primary Language: the locale you will use as your default
    Bundle ID: must match your Xcode project — select from the dropdown (populated
               from your Developer account). If it is not there, register it first
               in developer.apple.com → Certificates, IDs & Profiles → Identifiers.
    SKU: any unique internal string (e.g. "com.example.myapp-001"). Not shown publicly.
  Click Create. Note the numeric App ID — the agent will need this.

STEP 4 — COMPLETE THE AGE RATING QUESTIONNAIRE
  Go to App Store Connect → [your app] → App Information → Age Rating.
  Answer all questions about content (violence, language, gambling, etc.).
  Apple assigns the rating automatically from your answers.
  This is required before submission and cannot be done via API.

STEP 5 — DECLARE APP PRIVACY (NUTRITION LABELS)
  Go to App Store Connect → [your app] → App Privacy.
  Click Get Started and answer every question about data collection.
  If your app collects no data, select "No" to all and publish.
  Must be published before submission. Cannot be done via API.

STEP 6 — ADD A PRIVACY POLICY URL
  Go to App Store Connect → [your app] → App Information → Privacy Policy URL.
  Enter a live URL that is reachable from outside your network.
  This is a hard requirement — Apple will reject any app without one.

STEP 7 — CREATE THE FIRST APP STORE VERSION
  Go to App Store Connect → [your app] → (+) Version or Platform.
  Enter the version string (e.g. 1.0.0). This must match VERSION_NAME that you
  will pass to trigger_build later.
  You do not need to fill in screenshots or metadata now — the agent handles that.

---

WHAT THE AGENT HANDLES FROM HERE

Once the steps above are complete, the agent can:
  • Build and sign the IPA on Codemagic
  • Upload to TestFlight and App Store Connect
  • Set What's New text and other metadata
  • Validate and submit for review
  • Release and manage phased rollout

Use the /ios_release prompt to start the automated flow.
`.trim();

const FIRST_PUBLISH_ANDROID = `
# Android First Publish — One-Time Setup Checklist

This is the one-time human session before an agent can manage your Google Play releases.
Complete every item below, then use the /android_release workflow prompt for all future releases.

Estimated time: 15–30 minutes (plus identity verification, which can take up to 48 hours for new accounts).

---

STEP 1 — CREATE A GOOGLE PLAY DEVELOPER ACCOUNT
  Go to play.google.com/console and sign in with a Google account.
  Pay the one-time $25 registration fee.
  Complete identity verification. For new personal accounts, Google may take
  up to 48 hours to verify. You cannot publish until verification is complete.

STEP 2 — ACCEPT THE DEVELOPER DISTRIBUTION AGREEMENT
  Accept the agreement during registration or at the top of the Play Console
  dashboard if prompted.

STEP 3 — CREATE THE APP RECORD
  Go to Play Console → All apps → Create app.
  Fill in:
    App name: your app's display name
    Default language: the primary locale (e.g. English (United States))
    App or game: select the correct type
    Free or paid: choose carefully — you cannot switch from paid to free later
  Click Create app.

STEP 4 — COMPLETE THE CONTENT RATING QUESTIONNAIRE (IARC)
  Go to Policy → App content → Content rating.
  Click Start questionnaire and answer every question honestly.
  An incorrect rating can result in removal. Required before production release.
  Cannot be done via API.

STEP 5 — COMPLETE THE DATA SAFETY FORM
  Go to Policy → App content → Data safety.
  Declare what data the app collects, how it is used, and with whom it is shared.
  When complete, export the CSV (Export CSV button) and use set_android_data_safety
  to submit the declaration via the agent. Re-export and re-submit whenever your
  data practices change.

STEP 6 — SET UP APP ACCESS
  Go to Policy → App content → App access.
  If your app requires a login to use, select "All or some functionality is restricted"
  and provide working test credentials. Required for reviewers to evaluate the app.

STEP 7 — SET TARGET AUDIENCE AND CONTENT
  Go to Policy → App content → Target audience and content.
  Declare the target age group. If your app targets children, additional restrictions
  and family policies apply. Cannot be done via API.

STEP 8 — CLOSED TESTING PERIOD (new personal accounts only)
  Google requires NEW personal developer accounts to complete a closed testing period
  before production access is unlocked:
    • Create a closed (alpha) track release — Testing → Closed testing → Create track
    • Recruit at least 20 real testers who opt in via your testing link
    • Run the closed test for a minimum of 14 consecutive days
    • Apply for production access — Testing → Closed testing → [your track] → Request access
  This step does not apply to organisation accounts or accounts that have previously
  published apps. Check Play Console → Dashboard for any "Production access" banners.

---

WHAT THE AGENT HANDLES FROM HERE

Once the steps above are complete, the agent can:
  • Determine the next version code and trigger a signed build on Codemagic
  • Upload the AAB to the internal track
  • Promote through alpha → beta → production with staged rollout control
  • Update store listing text and screenshots
  • Submit and manage the data safety declaration

Use the /android_release prompt to start the automated flow.
`.trim();

const IOS_RELEASE_GUIDE = `
# iOS Release — Build to App Store
Prerequisites:
  - Distribution certificate and provisioning profile in Codemagic → Code signing → iOS certificates
  - ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY_B64 set in the environment
1. GET THE ASC APP ID
   Call list_asc_apps.
   Note the ASC app ID for your app — it is different from the Codemagic app ID.
2. DETERMINE THE NEXT BUILD NUMBER
   Call list_asc_builds with the ASC app ID.
   Find the highest build number. Increment by 1 — this is BUILD_NUMBER.
   Decide VERSION_NAME (e.g. "1.2.0").
3. CHECK RELEASE PIPELINE STATUS (optional but useful)
   Call get_asc_release_status to see the current state before starting.
4. GET THE RELEASE TEMPLATE
   Call get_yaml_template with the matching project type:
     ios, flutter, react-native, ionic-capacitor, ionic-cordova, kmm, dotnet-maui, etc.
   Replace bundle_identifier, XCODE_WORKSPACE, and XCODE_SCHEME with your app's values.
5. VALIDATE THE YAML
   Call validate_codemagic_yaml with the edited yaml.
6. TRIGGER THE BUILD
   Call trigger_build with:
     app_id (Codemagic app ID), workflow_id, branch
     yaml_content — the validated yaml
     variables    — { "BUILD_NUMBER": "42", "VERSION_NAME": "1.2.0" }
7. WAIT FOR THE BUILD
   Call wait_for_build. Note the IPA artifact URL on success.
8. SET EXPORT COMPLIANCE
   Call set_export_compliance with the ASC app ID.
   Most apps only use HTTPS/TLS — set uses_non_exempt_encryption=false.
9. UPLOAD TO TESTFLIGHT (beta / QA)
   Call upload_to_testflight with:
     app_id    — the ASC app ID from step 1
     ipa_url   — the IPA artifact URL from step 7
     beta_group (optional) — call list_testflight_groups to find available group names
   For external groups: call submit_beta_review with the build ID first (required by Apple).
10. UPLOAD BUILD TO APP STORE CONNECT
    Call upload_build_to_asc with the ASC app ID and IPA URL.
    Returns immediately — Apple processes the build in the background (10–30 min).
    Note the build ID returned.
11. WAIT FOR BUILD PROCESSING
    Call list_asc_builds repeatedly until the build's processingState is VALID.
    This typically takes 10–30 minutes. Calling this 20+ times is normal.
12. SET VERSION METADATA
    Call set_version_metadata with the ASC app ID, version, and locale.
    Provide whats_new — required by Apple for every release submission.
    Default locale is en-US; repeat for other supported locales if needed.
13. VALIDATE SUBMISSION
    Call validate_app_submission with the ASC app ID and version string.
    The result is an ordered remediation plan — fix the first blocker, then call again.
    Continue until the validation passes with no blockers.
14. SUBMIT FOR REVIEW
    Optional: for a phased rollout, call set_phased_release with action="create" first.
    Call submit_for_app_store_review with the ASC app ID, version, and build ID from step 10.
15. MONITOR REVIEW
    Call get_asc_review_status to track progress.
    Apple review typically takes 24–48 hours.
    When approved, the version enters "Pending Developer Release" state.
16. RELEASE
    Call release_version to release the version immediately.
    Or if you configured phased rollout in step 14, it starts automatically on release.
    To pause an in-progress rollout: call set_phased_release with action="pause".
    To complete it early: action="complete".
`.trim();

/**
 * Register MCP prompt resources — named, reusable workflow playbooks.
 * Agents can invoke these by name to get step-by-step instructions for
 * common Codemagic operations. Claude Desktop surfaces them as slash commands.
 * @param server - The MCP server instance.
 */
export function registerPrompts(server: McpServer): void {

  server.registerPrompt(
    "onboarding",
    { description: "Step-by-step guide to connect a repository to Codemagic and trigger a first debug build" },
    () => ({
      messages: [{ role: "user", content: { type: "text", text: ONBOARDING_GUIDE } }],
    })
  );

  server.registerPrompt(
    "android_release",
    { description: "Step-by-step guide to build a signed Android AAB on Codemagic and publish it to Google Play" },
    () => ({
      messages: [{ role: "user", content: { type: "text", text: ANDROID_RELEASE_GUIDE } }],
    })
  );

  server.registerPrompt(
    "ios_release",
    { description: "Step-by-step guide to build a signed iOS IPA on Codemagic and upload it to the App Store" },
    () => ({
      messages: [{ role: "user", content: { type: "text", text: IOS_RELEASE_GUIDE } }],
    })
  );

  server.registerPrompt(
    "first_publish_ios",
    { description: "One-time setup checklist for first-time iOS App Store publishers — walks through the UI steps the agent cannot do (Apple Developer enrollment, app record creation, age rating, privacy labels), then hands off to /ios_release" },
    () => ({
      messages: [{ role: "user", content: { type: "text", text: FIRST_PUBLISH_IOS } }],
    })
  );

  server.registerPrompt(
    "first_publish_android",
    { description: "One-time setup checklist for first-time Google Play publishers — walks through the UI steps the agent cannot do (account creation, content rating, closed testing period), then hands off to /android_release" },
    () => ({
      messages: [{ role: "user", content: { type: "text", text: FIRST_PUBLISH_ANDROID } }],
    })
  );

}