import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

function syntheticCsv(rows = 120): string {
  const header = [
    "Flow ID",
    "Source IP",
    "Destination IP",
    "Source Port",
    "Destination Port",
    "Protocol",
    "Timestamp",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Label",
  ];
  const body = Array.from({ length: rows }, (_, index) => {
    const attack = index % 6 === 0;
    const minute = String(Math.floor(index / 6)).padStart(2, "0");
    const second = String((index * 7) % 60).padStart(2, "0");
    return [
      `flow-${index}`,
      `10.0.0.${index % 200}`,
      `192.168.1.${(index * 3) % 200}`,
      String(40000 + index),
      attack ? "443" : "80",
      "6",
      `2026-01-01 00:${minute}:${second}`,
      String(1000 + index * 11),
      String(4 + (index % 20)),
      String(3 + (index % 17)),
      String(500 + index * 13),
      String(400 + index * 9),
      String(800 + index * 17),
      String(10 + (index % 50)),
      attack ? "DDoS" : "BENIGN",
    ].join(",");
  });
  return [header.join(","), ...body].join("\n");
}

async function accessibilityViolations(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  return result.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test("landing page has no serious accessibility violations", async ({ page }) => {
  const errors: Error[] = [];
  page.on("pageerror", (error) => errors.push(error));
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /先跑一次/ })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expect(await accessibilityViolations(page)).toEqual([]);
  expect(errors).toEqual([]);
});

test("upload preflight explains mapping and split coverage", async ({ page }) => {
  await page.goto("/");
  await page.getByText("上传文件", { exact: true }).click();
  await page.locator('input[name="flow-file"]').setInputFiles({
    name: "preflight.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(syntheticCsv()),
  });
  await page.getByRole("button", { name: "预检数据与切分" }).click();

  await expect(page.getByRole("heading", { name: "先核对，再训练。" })).toBeVisible();
  await expect(page.getByText("数据与切分通过预检")).toBeVisible();
  await expect(page.getByRole("heading", { name: "切分后覆盖" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始完整评估" })).toBeEnabled();
  await expectNoHorizontalOverflow(page);
  expect(await accessibilityViolations(page)).toEqual([]);
});

test("mobile configuration drawer is keyboard closable and accessible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const trigger = page.getByRole("button", { name: "配置", exact: true });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "实验配置" });
  await expect(dialog).toBeVisible();

  await expectNoHorizontalOverflow(page);
  expect(await accessibilityViolations(page)).toEqual([]);

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("a small synthetic experiment completes and renders metrics", async ({ page }) => {
  const errors: Error[] = [];
  page.on("pageerror", (error) => errors.push(error));
  await page.goto("/");

  await page.getByRole("checkbox", { name: /mlp/ }).uncheck();
  await page.getByRole("checkbox", { name: /autoencoder/ }).uncheck();
  await page.getByRole("spinbutton", { name: "正常流" }).fill("150");
  await page.getByRole("spinbutton", { name: "攻击流" }).fill("30");
  await page.getByRole("button", { name: "用当前配置跑一次" }).click();

  await expect(page.getByRole("heading", { name: /模型对比/ })).toBeVisible({
    timeout: 40_000,
  });
  await expect(page.getByText("验证集最佳")).toBeVisible();
  await expect(page.getByText("AUC", { exact: true }).first()).toBeVisible();
  expect(errors).toEqual([]);
});
