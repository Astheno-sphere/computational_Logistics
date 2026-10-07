import { expect, test } from "@playwright/test";

test("api client keeps a Postman-like vertical workbench layout", async ({
  page,
}, testInfo) => {
  const consoleErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    consoleErrors.push(error.message);
  });

  await page.setViewportSize({ height: 900, width: 1440 });
  await page.goto("/");

  const moduleNav = page.getByRole("navigation", { name: "Modules" });
  await expect(moduleNav).toBeVisible();
  await moduleNav.getByRole("button", { name: "API" }).click();

  await expect(
    page.getByRole("tablist", { name: "Open API requests" }),
  ).toBeVisible();
  await expect(page.getByLabel("Request URL")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Send$/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Save$/i })).toBeVisible();

  await expect(page.getByText("Search or run command")).toHaveCount(0);
  await expect(page.getByText(/^unsaved$/i)).toHaveCount(0);

  const requestAnchor = page.getByLabel("Request URL");
  const responseEmptyState = page.getByText("No response yet");
  await expect(requestAnchor).toBeVisible();
  await expect(responseEmptyState).toBeVisible();

  const requestBox = await requestAnchor.boundingBox();
  const responseBox = await responseEmptyState.boundingBox();
  expect(requestBox).not.toBeNull();
  expect(responseBox).not.toBeNull();
  expect(responseBox!.y).toBeGreaterThan(requestBox!.y + 60);

  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("api-client-layout.png"),
  });

  expect(consoleErrors).toEqual([]);
});
