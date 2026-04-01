import { Octokit } from "@octokit/rest";

export async function getRepoContent(token: string | null, repoUrl: string) {
  const octokit = new Octokit(token ? { auth: token } : {});

  const match = repoUrl.match(/(?:github\.com\/)?([^/]+)\/([^/\s]+)/);
  if (!match) throw new Error("Invalid repo format. Use owner/repo or full GitHub URL.");
  const owner = match[1];
  const repo = match[2].replace(/\.git$/, "");

  const { data: repoData } = await octokit.repos.get({ owner, repo });

  let readme = "";
  try {
    const { data } = await octokit.repos.getReadme({ owner, repo });
    readme = Buffer.from(data.content, "base64").toString("utf-8");
  } catch {}

  let packageJson = "";
  try {
    const { data } = await octokit.repos.getContent({ owner, repo, path: "package.json" });
    if ("content" in data) {
      packageJson = Buffer.from(data.content, "base64").toString("utf-8");
    }
  } catch {}

  const { data: tree } = await octokit.git.getTree({
    owner,
    repo,
    tree_sha: repoData.default_branch,
    recursive: "1",
  });
  const paths = tree.tree
    .filter((t) => t.type === "blob")
    .map((t) => t.path)
    .slice(0, 200);

  return {
    name: repoData.name,
    description: repoData.description || "",
    language: repoData.language || "",
    topics: repoData.topics || [],
    stars: repoData.stargazers_count,
    readme,
    packageJson,
    fileTree: paths,
  };
}
