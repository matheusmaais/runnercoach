import { expect, test } from "@playwright/test";

test("renders cockpit with athlete evidence boundaries", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Meia Forte Janeiro 2027" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /No caminho da meia forte/ })).toBeVisible();
  await expect(page.getByText("Quarentenado: dado Garmin/Matheus")).toBeVisible();
  await expect(page.getByText(/Evidência Bruna:/)).toBeVisible();
});

test("navigates through all product sections", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Timeline" }).click();
  await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();
  await expect(page.getByText("Garmin Matheus: não usar como evolução da Bruna.").first()).toBeVisible();

  await page.getByRole("button", { name: "Plano" }).click();
  await expect(page.getByRole("heading", { name: "Plano ligado ao que já aconteceu" })).toBeVisible();

  await page.getByRole("button", { name: "Coach Room" }).click();
  await expect(page.getByRole("heading", { name: "Coach Room" })).toBeVisible();
  await expect(page.getByText("Claims proibidos")).toBeVisible();

  await page.getByRole("button", { name: "Ciência" }).click();
  await expect(page.getByRole("heading", { name: "Ciência & Decisões" })).toBeVisible();
  await expect(page.getByText("Fonte").first()).toBeVisible();
});
