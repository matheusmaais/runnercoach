import type { GithubSettings } from "./operational";

type CommitFileArgs = {
  settings: GithubSettings;
  path: string;
  content: string;
  message: string;
};

export async function commitFileToGithub({ settings, path, content, message }: CommitFileArgs) {
  const baseUrl = `https://api.github.com/repos/${settings.owner}/${settings.repo}/contents/${encodeURIComponentPath(path)}`;
  const current = await fetch(`${baseUrl}?ref=${encodeURIComponent(settings.branch)}`, {
    headers: githubHeaders(settings.token),
  });
  const existing = current.ok ? await current.json() : null;

  const response = await fetch(baseUrl, {
    method: "PUT",
    headers: githubHeaders(settings.token),
    body: JSON.stringify({
      message,
      content: btoa(unescape(encodeURIComponent(content))),
      branch: settings.branch,
      sha: existing?.sha,
    }),
  });

  if (!response.ok) {
    throw new Error(`GitHub commit falhou: HTTP ${response.status} ${await response.text()}`);
  }
  return response.json();
}

export async function dispatchOperationalWorkflow(settings: GithubSettings, intakePath: string) {
  const response = await fetch(
    `https://api.github.com/repos/${settings.owner}/${settings.repo}/actions/workflows/operational-intake.yml/dispatches`,
    {
      method: "POST",
      headers: githubHeaders(settings.token),
      body: JSON.stringify({
        ref: settings.branch,
        inputs: {
          intake_path: intakePath,
          run_llm: "true",
          commit_results: "true",
        },
      }),
    },
  );

  if (!response.ok) {
    throw new Error(`Workflow dispatch falhou: HTTP ${response.status} ${await response.text()}`);
  }
}

function githubHeaders(token: string) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function encodeURIComponentPath(path: string) {
  return path.split("/").map(encodeURIComponent).join("/");
}
