import { expect, test } from "@playwright/test";

test("app shell renders and module switching stays stable", async ({ page }) => {
  const consoleErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    consoleErrors.push(error.message);
  });

  await page.goto("/");

  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("button", { name: /default workspace/i })).toBeVisible();

  const moduleNav = page.getByRole("navigation", { name: "Modules" });
  await expect(moduleNav).toBeVisible();
  await expect(moduleNav.getByRole("button", { name: "API" })).toHaveAttribute(
    "title",
    "API Client",
  );
  await expect(moduleNav.getByRole("button", { name: "SSH" })).toHaveAttribute(
    "title",
    "SSH Terminal",
  );
  await expect(
    moduleNav.getByRole("button", { name: "Database" }),
  ).toHaveAttribute("title", "Database");

  const moduleLabels: Record<string, string> = {
    API: "API Client",
    SSH: "SSH Terminal",
    DB: "Database",
  };
  for (const label of Object.values(moduleLabels)) {
    await moduleNav.getByRole("button", { name: label }).click();
    await expect(page.locator(".app-shell")).toBeVisible();
  }

  expect(consoleErrors).toEqual([]);
});
