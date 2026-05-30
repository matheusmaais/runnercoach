import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const appData = JSON.parse(readFileSync(new URL("../public/data/app-data.json", import.meta.url), "utf-8"));

test("renders cockpit with athlete evidence boundaries", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Meia Forte Janeiro 2027" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /No caminho da meia forte/ })).toBeVisible();
  await expect(page.getByText("Quarentenado: dado Garmin/Matheus")).toBeVisible();
  await expect(page.getByText(/Evidência Bruna:/)).toBeVisible();
});

test("renders actionable cockpit risk drivers and chart units", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Risco atual")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Moderado" })).toBeVisible();
  await expect(page.getByText(/Vôlei no dia anterior/)).toBeVisible();

  await expect(page.getByRole("heading", { name: "Pace médio (min/km)" })).toBeVisible();
  await expect(page.getByText("Ritmo médio em minutos por quilômetro.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Volume semanal (km)" })).toBeVisible();
  await expect(page.getByText("Distância semanal em km.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Qualidade semanal (treinos)" })).toBeVisible();
  await expect(page.getByText("Treinos de qualidade por semana.")).toBeVisible();
});

test("cockpit does not overflow horizontally on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 851 });
  await page.goto("/");

  await expect.poll(async () =>
    page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
  ).toBe(true);
});

test("navigates through all product sections", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Histórico" }).click();
  await expect(page.getByRole("heading", { name: "Histórico" })).toBeVisible();
  await expect(page.getByText("Garmin Matheus: não usar como evolução da Bruna.").first()).toBeVisible();

  await page.getByRole("button", { name: "Plano" }).click();
  await expect(page.getByRole("heading", { name: "O que fazer esta semana" })).toBeVisible();

  await page.getByRole("button", { name: "Sala do coach" }).click();
  await expect(page.getByRole("heading", { name: "Sala do coach" })).toBeVisible();
  const recommendationPanel = page.locator(".recommendation-panel");
  await expect(recommendationPanel.getByRole("heading", { name: "Recomendação validada" })).toBeVisible();
  await expect(recommendationPanel.getByText("reduce next workout")).toBeVisible();
  await expect(recommendationPanel.getByText("Evidência usada")).toBeVisible();
  await expect(recommendationPanel.getByText("Evidência faltante")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Histórico de recomendações" })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Revisão legível" })).toBeVisible();
  await expect(page.getByText("Será versionado em")).toBeVisible();
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
              created_at: new Date().toISOString(),
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

  await page.getByRole("button", { name: "Salvar e ver minha semana" }).click();
  await expect(page.getByRole("list", { name: "Progresso operacional" }).getByText("Workflow em fila no GitHub Actions.")).toBeVisible();

  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("runnercoach.github"))).toBeNull();
});

test("operational submit polls workflow to success and reloads coach payload", async ({ page }) => {
  let appDataRequests = 0;
  let runPolls = 0;
  const runUrl = "https://github.com/matheusmaais/runnercoach/actions/runs/777";

  await page.route("**/data/app-data.json**", async (route) => {
    appDataRequests += 1;
    const payload = structuredClone(appData);
    if (appDataRequests > 1 && payload.latest_llm_recommendation) {
      payload.latest_llm_recommendation.summary = "Nova recomendação operacional recarregada sem refresh manual.";
      payload.latest_llm_recommendation.next_workout = "Coach Room atualizado pelo workflow concluído.";
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.route("https://api.github.com/**", async (route) => {
    const request = route.request();
    if (request.url().includes("/runs?")) {
      runPolls += 1;
      const status = runPolls === 1 ? "queued" : runPolls === 2 ? "in_progress" : "completed";
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          workflow_runs: [
            {
              id: 777,
              html_url: runUrl,
              status,
              conclusion: status === "completed" ? "success" : null,
              created_at: new Date().toISOString(),
            },
          ],
        }),
      });
      return;
    }
    if (request.method() === "POST") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ sha: "mock-sha" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Operar" }).click();
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

  await page.getByRole("button", { name: "Salvar e ver minha semana" }).click();
  const progress = page.getByRole("list", { name: "Progresso operacional" });
  await expect(page.getByText("Commit/payload")).toBeVisible();
  await expect(progress.getByText("Workflow", { exact: true })).toBeVisible();
  await expect(page.getByText("LLM/validação")).toBeVisible();
  await expect(page.getByText("Publicação")).toBeVisible();
  await expect(progress.getByText(/Workflow em fila|Workflow rodando/)).toBeVisible();
  await expect(page.getByText("Workflow concluído com sucesso.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Abrir run no GitHub Actions" })).toHaveAttribute("href", runUrl);
  await expect(page.getByRole("button", { name: "Ver plano da semana" })).toBeVisible();

  await expect.poll(() => runPolls).toBeGreaterThanOrEqual(3);
  await expect.poll(() => appDataRequests).toBeGreaterThanOrEqual(2);
  await expect(page.getByText("OPENAI_API_KEY")).toHaveCount(0);

  await page.getByRole("button", { name: "Ver plano da semana" }).click();
  await expect(page.getByRole("heading", { name: "O que fazer esta semana" })).toBeVisible();
});

test("operational submit failure keeps the Actions URL actionable", async ({ page }) => {
  const runUrl = "https://github.com/matheusmaais/runnercoach/actions/runs/778";

  await page.route("https://api.github.com/**", async (route) => {
    const request = route.request();
    if (request.url().includes("/runs?")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          workflow_runs: [
            {
              id: 778,
              html_url: runUrl,
              status: "completed",
              conclusion: "failure",
              created_at: new Date().toISOString(),
            },
          ],
        }),
      });
      return;
    }
    if (request.method() === "POST") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ sha: "mock-sha" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Operar" }).click();
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

  await page.getByRole("button", { name: "Salvar e ver minha semana" }).click();

  await expect(page.getByText("Workflow falhou: failure. Abra o run no GitHub Actions para ver logs e rerun.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Abrir run no GitHub Actions" })).toHaveAttribute("href", runUrl);
  await expect(page.getByRole("button", { name: "Salvar e ver minha semana" })).toBeVisible();
});

test("cockpit shows a single PT-BR 'what to do today' directive", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("O que fazer hoje")).toBeVisible();
});

test("Plano shows the week-ahead (Semana) in PT-BR", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Plano" }).click();
  await expect(page.getByRole("heading", { name: "O que fazer esta semana" })).toBeVisible();
  await expect(page.getByText("Próximo treino", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Semana", exact: true })).toBeVisible();
  await expect(page.getByText("Seg", { exact: true })).toBeVisible();
  await expect(page.getByText("Dom", { exact: true })).toBeVisible();
});

test("Operar shows a race entry form that validates input", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Operar" }).click();
  await expect(page.getByRole("heading", { name: "Adicionar prova (balizador)" })).toBeVisible();
  // invalid (empty distance/time) keeps the save button disabled
  await page.getByLabel("Distância (km)").fill("");
  await page.getByLabel("Tempo (mm:ss ou h:mm:ss)").fill("");
  await expect(page.getByRole("button", { name: "Salvar prova e recalibrar zonas" })).toBeDisabled();
  // valid input enables it and shows the target path
  await page.getByLabel("Distância (km)").fill("5");
  await page.getByLabel("Tempo (mm:ss ou h:mm:ss)").fill("29:10");
  await expect(page.getByText(/Prova pronta para salvar em/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Salvar prova e recalibrar zonas" })).toBeEnabled();
});

test("race-only submit commits and dispatches the workflow without Garmin", async ({ page }) => {
  let posts = 0;
  await page.route("https://api.github.com/**", async (route) => {
    const request = route.request();
    if (request.url().includes("/runs?")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          workflow_runs: [{ id: 99, html_url: "https://github.com/matheusmaais/runnercoach/actions/runs/99", status: "queued", conclusion: null, created_at: new Date().toISOString() }],
        }),
      });
      return;
    }
    if (request.method() === "POST" || request.method() === "PUT") {
      posts += 1;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ content: { sha: "x" } }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ sha: "mock-sha" }) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Operar" }).click();
  await page.getByLabel("Token").fill("ghp_token");
  await page.getByLabel("Distância (km)").fill("5");
  await page.getByLabel("Tempo (mm:ss ou h:mm:ss)").fill("29:10");
  await page.getByRole("button", { name: "Salvar prova e recalibrar zonas" }).click();
  await expect.poll(() => posts).toBeGreaterThanOrEqual(1);
});

test("progression nudge renders when the coach suggests a 4th day", async ({ page }) => {
  await page.route("**/data/app-data.json**", async (route) => {
    const payload = structuredClone(appData);
    payload.progression_suggestion = {
      should_suggest: true,
      message: "Você está absorvendo bem há 6 semanas. Considere adicionar um 4º dia de corrida LEVE.",
      science_refs: ["load-management-recovery", "seiler-intensity-distribution"],
    };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/");
  await expect(page.getByText(/adicionar um 4º dia de corrida LEVE/)).toBeVisible();
});
