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
  await expect(page.getByRole("heading", { name: "Recomendação validada" })).toBeVisible();
  await expect(page.getByText("reduce next workout")).toBeVisible();
  await expect(page.getByText("Claims proibidos")).toBeVisible();

  await page.getByRole("button", { name: "Ciência" }).click();
  await expect(page.getByRole("heading", { name: "Ciência & Decisões" })).toBeVisible();
  await expect(page.getByText("Fonte").first()).toBeVisible();
});

test("operational frontend builds a valid intake without exposing LLM secrets", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Operar" }).click();
  await expect(page.getByRole("heading", { name: "Inserir treino e disparar análise" })).toBeVisible();
  await expect(page.getByText("A LLM roda apenas no Actions com secret")).toBeVisible();

  await page.getByLabel("PSE Bruna").fill("6");
  await page.getByLabel("Relato Bruna").fill("Controlado e sem sintomas fortes.");
  await page.getByLabel("Upload Garmin CSV").setInputFiles({
    name: "Activities.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Tipo de atividade,Data,Título,Distância,Tempo,Ritmo médio,Melhor ritmo\n" +
        "Corrida,2026-05-29 18:00:00,Treino UI,7.00,00:45:00,6:26,5:55\n",
    ),
  });
  await expect(page.getByLabel("Activity ID Garmin (avancado/opcional)")).toHaveValue(/garmin-20260529T180000/);
  await expect(page.getByLabel("Título Garmin")).toHaveValue("Treino UI");
  await expect(page.getByText("CSV lido localmente; o intake inclui apenas resumo sanitizado.")).toBeVisible();
  await expect(page.getByText("Payload válido para commit e workflow.")).toBeVisible();
  await expect(page.getByText("OPENAI_API_KEY")).toHaveCount(0);
  await expect(page.getByText('"source": "github_pages"')).toBeVisible();
  await expect(page.getByText('"garmin_activity"')).toBeVisible();
  await expect(page.getByText("content_base64")).toHaveCount(0);
});

test("operational GitHub token stays in memory and defaults to the runnercoach owner", async ({ page }) => {
  await page.route("https://api.github.com/**", async (route) => {
    const request = route.request();
    if (request.url().includes("/runs?")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          workflow_runs: [
            {
              id: 123,
              html_url: "https://github.com/matheusmaais/runnercoach/actions/runs/123",
              status: "queued",
              conclusion: null,
              created_at: "2026-05-29T12:00:00Z",
            },
          ],
        }),
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ sha: "mock-sha" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Operar" }).click();

  await expect(page.getByLabel("Owner")).toHaveValue("matheusmaais");
  await expect(page.getByText("Token fica apenas na memória desta aba e não é salvo no navegador.")).toBeVisible();

  await page.getByLabel("PSE Bruna").fill("6");
  await page.getByLabel("Relato Bruna").fill("Controlado e sem sintomas fortes.");
  await page.getByLabel("Upload Garmin CSV").setInputFiles({
    name: "Activities.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Tipo de atividade,Data,Título,Distância,Tempo,Ritmo médio,Melhor ritmo\n" +
        "Corrida,2026-05-29 18:00:00,Treino UI,7.00,00:45:00,6:26,5:55\n",
    ),
  });
  await page.getByLabel("Token").fill("ghp_should_not_persist");

  await page.getByRole("button", { name: "Commitar intake e analisar" }).click();
  await expect(page.getByText(/Workflow queued disparado/)).toBeVisible();

  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("runnercoach.github"))).toBeNull();
});
