import { expect, test, type Page } from "@playwright/test";

const apiBase =
  process.env.CLOUD_BACKEND_API_URL ||
  "https://cs6604-trafficsafety-180117512369.europe-west1.run.app/api/v1";

function significantConsoleErrors(page: Page) {
  const messages: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (/favicon|ResizeObserver loop/i.test(text)) return;
    messages.push(text);
  });
  page.on("pageerror", (error) => messages.push(error.message));
  return messages;
}

async function waitForLiveDashboard(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Safety dashboard" })).toBeVisible();
  await expect(page.getByText("Live backend data")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText("Fallback sample data")).toHaveCount(0);
}

async function expectNoTopLevelOverlap(page: Page) {
  const overlaps = await page.evaluate(() => {
    const selectors = [".nav-rail", ".workspace", ".chat-dock"];
    const boxes = selectors
      .map((selector) => {
        const element = document.querySelector<HTMLElement>(selector);
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
          selector,
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          area: rect.width * rect.height
        };
      })
      .filter((box): box is NonNullable<typeof box> => Boolean(box));

    const failures: string[] = [];
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
        const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        const overlapArea = width * height;
        const ratio = overlapArea / Math.max(1, Math.min(a.area, b.area));
        if (ratio > 0.02) failures.push(`${a.selector} overlaps ${b.selector} by ${Math.round(ratio * 100)}%`);
      }
    }
    return failures;
  });

  expect(overlaps).toEqual([]);
}

test("cloud dashboard loads live backend data and core UI", async ({ page }) => {
  const consoleErrors = significantConsoleErrors(page);

  await waitForLiveDashboard(page);

  await expect(page.getByRole("heading", { name: "Network risk map" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Intersections" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "SafetyChat" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Operations" })).toHaveClass(/active/);
  await expectNoTopLevelOverlap(page);
  expect(consoleErrors).toEqual([]);
});

test("network risk map renders road tiles and visible intersection markers", async ({ page }) => {
  await waitForLiveDashboard(page);

  const map = page.locator(".geo-plot");
  await expect(map).toBeVisible();

  await page.waitForFunction(() => {
    const tiles = Array.from(document.querySelectorAll<HTMLImageElement>(".geo-plot img.map-tile"));
    return tiles.some((tile) => tile.complete && tile.naturalWidth > 0 && tile.naturalHeight > 0);
  });

  expect(await map.locator("img.map-tile").count()).toBeGreaterThan(0);
  await expect(map.locator(".map-marker").first()).toBeVisible();

  const markerStats = await page.evaluate(() => {
    const mapRect = document.querySelector(".geo-plot")?.getBoundingClientRect();
    const markers = Array.from(document.querySelectorAll<HTMLElement>(".geo-plot .map-marker"));
    if (!mapRect) return { count: 0, outside: 0, zeroSize: 0 };
    return markers.reduce(
      (stats, marker) => {
        const rect = marker.getBoundingClientRect();
        const outside =
          rect.right < mapRect.left ||
          rect.left > mapRect.right ||
          rect.bottom < mapRect.top ||
          rect.top > mapRect.bottom;
        return {
          count: stats.count + 1,
          outside: stats.outside + (outside ? 1 : 0),
          zeroSize: stats.zeroSize + (rect.width <= 0 || rect.height <= 0 ? 1 : 0)
        };
      },
      { count: 0, outside: 0, zeroSize: 0 }
    );
  });

  expect(markerStats.count).toBeGreaterThan(0);
  expect(markerStats.outside).toBe(0);
  expect(markerStats.zeroSize).toBe(0);
});

test("dashboard navigation reaches all major cloud-backed panels", async ({ page }) => {
  await waitForLiveDashboard(page);

  await page.getByRole("button", { name: "Trends" }).click();
  await expect(page.getByRole("heading", { name: "Trend analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Load range" })).toBeEnabled();

  await page.getByRole("button", { name: "Validation" }).click();
  await expect(page.getByRole("heading", { name: "Analytics and validation" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run validation" })).toBeEnabled();

  await page.getByRole("button", { name: "Sensitivity" }).click();
  await expect(page.getByRole("heading", { name: "Sensitivity analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run analysis" })).toBeEnabled();

  await page.getByRole("button", { name: "Database" }).click();
  await expect(page.getByRole("heading", { name: "Database explorer" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Load table" })).toBeEnabled();
});

test("frontend build points at the expected backend API", async ({ request }) => {
  const response = await request.get(`${apiBase}/safety/index/intersections/list`, {
    timeout: 45_000
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(Array.isArray(body.intersections)).toBeTruthy();
  expect(body.intersections.length).toBeGreaterThan(0);
});
