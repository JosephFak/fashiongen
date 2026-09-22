/* Run against a running demo server: npm run test:e2e */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}),
    ...(process.env.CHROMIUM_ARGS ? { args: JSON.parse(process.env.CHROMIUM_ARGS) } : {}),
  });
  const baseURL = process.env.BASE_URL || "http://127.0.0.1:8888";
  const screenshots = process.env.SCREENSHOT_DIR;
  if (screenshots) fs.mkdirSync(screenshots, { recursive: true });
  const errors = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(baseURL);
    await page.waitForFunction(() => !document.getElementById("drop-zone").disabled);
    assert.match(await page.locator("#generation-mode").innerText(), /Demo/);
    assert.equal(await page.locator("#search-button").isDisabled(), true);
    await page.getByRole("button", { name: "Blue & white sneakers", exact: true }).click();
    await page.locator("#generate-button").click();
    await page.locator("#preview-image").waitFor({ state: "visible" });
    await page.waitForFunction(() => !document.getElementById("search-button").disabled);
    assert.match(await page.locator("#image-caption").innerText(), /Demo image/);
    if (screenshots) await page.screenshot({ path: path.join(screenshots, "workspace.png"), fullPage: true });
    await page.locator("#search-button").click();
    await page.waitForFunction(() => document.querySelectorAll(".result-card").length === 6);
    assert.equal(await page.locator("#page-indicator").innerText(), "Page 1 of 3");
    assert.equal(await page.locator("#previous-page").isDisabled(), true);
    assert.match(await page.locator("#results-summary").innerText(), /14 sample items/);
    assert.ok(await page.locator(".premium-badge").count() > 0);
    assert.equal(await page.locator(".view-item").first().getAttribute("target"), "_blank");
    if (screenshots) await page.screenshot({ path: path.join(screenshots, "desktop.png"), fullPage: true });
    await page.locator("#next-page").click();
    assert.equal(await page.locator("#page-indicator").innerText(), "Page 2 of 3");
    await page.locator("#next-page").click();
    assert.equal(await page.locator(".result-card").count(), 2);
    assert.equal(await page.locator("#next-page").isDisabled(), true);
    const longTitle = page.locator(".result-title").filter({ hasText: "extended descriptive title" });
    assert.equal(await longTitle.count(), 1);
    assert.equal(await longTitle.evaluate((node) => node.scrollHeight <= node.clientHeight), true);
    await page.locator("#previous-page").click();
    assert.equal(await page.locator(".result-card").count(), 6);

    // A real image upload must replace the selected image and clear old results.
    const png = await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 64; canvas.height = 64;
      const ctx = canvas.getContext("2d"); ctx.fillStyle = "blue"; ctx.fillRect(0, 0, 64, 64);
      return canvas.toDataURL("image/png").split(",")[1];
    });
    await page.locator("#image-file").setInputFiles({ name: "sketch.png", mimeType: "image/png", buffer: Buffer.from(png, "base64") });
    await page.waitForFunction(() => document.getElementById("file-caption").textContent === "sketch.png");
    assert.equal(await page.locator("#results-section").isHidden(), true);
    await page.locator("#search-button").click();
    await page.waitForFunction(() => document.querySelectorAll(".result-card").length === 6);

    // Live failures are shown as errors, never substituted with demo matches.
    await page.route("**/api/image-search", (route) => route.fulfill({
      status: 502, contentType: "application/json", body: JSON.stringify({ error: "Search provider unavailable." }),
    }));
    await page.locator("#search-button").click();
    await page.locator("#error-message").waitFor({ state: "visible" });
    assert.match(await page.locator("#error-message").innerText(), /provider unavailable/);
    await page.waitForFunction(() => !document.getElementById("search-button").disabled);
    assert.equal(await page.locator(".result-card").count(), 0);
    await page.unroute("**/api/image-search");
    await page.locator("#clear-image").click();
    assert.equal(await page.locator("#search-button").isDisabled(), true);
    await page.locator("#image-file").setInputFiles({ name: "wrong.txt", mimeType: "text/plain", buffer: Buffer.from("not an image") });
    await page.locator("#error-message").waitFor({ state: "visible" });
    assert.match(await page.locator("#error-message").innerText(), /PNG, JPG, or WebP/);

    // Small screens preserve all controls and avoid horizontal overflow.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await page.waitForFunction(() => !document.getElementById("drop-zone").disabled);
    await page.locator(".example-chip").first().click();
    await page.locator("#generate-button").click();
    await page.waitForFunction(() => !document.getElementById("search-button").disabled);
    await page.locator("#search-button").click();
    await page.waitForFunction(() => document.querySelectorAll(".result-card").length === 6);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    if (screenshots) await page.screenshot({ path: path.join(screenshots, "mobile.png"), fullPage: true });
    assert.deepEqual(errors, []);
    console.log("PASS: generation, search, premium ranking, 3-page navigation, full titles, upload, reset, errors, and mobile layout.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
