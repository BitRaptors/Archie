import { describe, it, expect } from "vitest";
import {
  parseReadmeSections,
  extractDependencies,
  inferProjectType,
  mapReadmeToLandingPageSections,
  buildPrompt,
  buildClaudePrompt,
} from "./generate";

// ---------------------------------------------------------------------------
// parseReadmeSections
// ---------------------------------------------------------------------------
describe("parseReadmeSections", () => {
  it("splits by markdown headings", () => {
    const readme = `# Intro\nHello world\n## Features\n- Fast\n- Simple\n### Sub\nDetails`;
    const result = parseReadmeSections(readme);
    expect(result).toHaveProperty("intro");
    expect(result).toHaveProperty("features");
    expect(result).toHaveProperty("sub");
    expect(result["intro"]).toBe("Hello world");
    expect(result["features"]).toContain("Fast");
  });

  it("returns { overview: readme } when no headings found", () => {
    const readme = "Just plain text with no headings.";
    const result = parseReadmeSections(readme);
    expect(result).toEqual({ overview: readme });
  });

  it("handles empty string", () => {
    const result = parseReadmeSections("");
    expect(result).toEqual({ overview: "" });
  });

  it("lowercases headings", () => {
    const result = parseReadmeSections("# Getting Started\nStep 1");
    expect(result).toHaveProperty("getting started");
  });

  it("captures content before first heading as overview", () => {
    const readme = "Preamble text\n# Section\nBody";
    const result = parseReadmeSections(readme);
    expect(result["overview"]).toBe("Preamble text");
    expect(result["section"]).toBe("Body");
  });
});

// ---------------------------------------------------------------------------
// extractDependencies
// ---------------------------------------------------------------------------
describe("extractDependencies", () => {
  it("extracts prod and dev dependencies", () => {
    const pkg = JSON.stringify({
      dependencies: { react: "^18.0.0", next: "^14.0.0" },
      devDependencies: { typescript: "^5.0.0", vitest: "^1.0.0" },
    });
    const result = extractDependencies(pkg);
    expect(result.prod).toEqual(["react", "next"]);
    expect(result.dev).toEqual(["typescript", "vitest"]);
  });

  it("returns empty arrays for empty string", () => {
    expect(extractDependencies("")).toEqual({ prod: [], dev: [] });
  });

  it("returns empty arrays for invalid JSON", () => {
    expect(extractDependencies("{broken")).toEqual({ prod: [], dev: [] });
  });

  it("handles missing dependency keys", () => {
    const pkg = JSON.stringify({ name: "test", version: "1.0.0" });
    const result = extractDependencies(pkg);
    expect(result.prod).toEqual([]);
    expect(result.dev).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// inferProjectType
// ---------------------------------------------------------------------------
describe("inferProjectType", () => {
  it("detects React + TypeScript", () => {
    const result = inferProjectType(["react", "typescript"], ["src/App.tsx"]);
    expect(result).toContain("React");
    expect(result).toContain("TypeScript");
  });

  it("detects Next.js", () => {
    const result = inferProjectType(["next", "react"], []);
    expect(result).toContain("Next.js");
  });

  it("detects Rust from file tree", () => {
    const result = inferProjectType([], ["Cargo.toml", "src/main.rs"]);
    expect(result).toContain("Rust");
  });

  it("detects Go from file tree", () => {
    const result = inferProjectType([], ["go.mod", "main.go"]);
    expect(result).toContain("Go");
  });

  it("detects Python from requirements.txt", () => {
    const result = inferProjectType([], ["requirements.txt", "app.py"]);
    expect(result).toContain("Python");
  });

  it("detects TypeScript from .ts files in tree even without dep", () => {
    const result = inferProjectType([], ["src/index.ts", "src/utils.ts"]);
    expect(result).toContain("TypeScript");
  });

  it("returns 'Software project' when no signals found", () => {
    expect(inferProjectType([], [])).toBe("Software project");
  });

  it("detects Express backend", () => {
    const result = inferProjectType(["express", "cors"], []);
    expect(result).toContain("Express");
  });
});

// ---------------------------------------------------------------------------
// mapReadmeToLandingPageSections
// ---------------------------------------------------------------------------
describe("mapReadmeToLandingPageSections", () => {
  it("maps feature headings to Features/Benefits", () => {
    const result = mapReadmeToLandingPageSections({
      features: "- Fast\n- Reliable",
      "getting started": "npm install",
    });
    expect(result["Features/Benefits"]).toContain("Fast");
    expect(result["How It Works"]).toContain("npm install");
  });

  it("maps 'why' heading to Problem/Pain", () => {
    const result = mapReadmeToLandingPageSections({
      "why this tool": "Existing tools are slow",
    });
    expect(result["Problem/Pain"]).toContain("slow");
  });

  it("maps usage to Solution/Demo", () => {
    const result = mapReadmeToLandingPageSections({
      "usage examples": "const x = doStuff()",
    });
    expect(result["Solution/Demo"]).toContain("doStuff");
  });

  it("maps faq heading", () => {
    const result = mapReadmeToLandingPageSections({
      faq: "Q: Does it work?\nA: Yes",
    });
    expect(result["FAQ"]).toContain("Does it work");
  });

  it("returns empty object when no headings match", () => {
    const result = mapReadmeToLandingPageSections({
      license: "MIT",
      contributing: "PRs welcome",
    });
    expect(Object.keys(result)).toHaveLength(0);
  });

  it("truncates long sections to 2000 chars", () => {
    const longContent = "x".repeat(5000);
    const result = mapReadmeToLandingPageSections({ features: longContent });
    expect(result["Features/Benefits"].length).toBe(2000);
  });
});

// ---------------------------------------------------------------------------
// buildPrompt — full integration
// ---------------------------------------------------------------------------
describe("buildPrompt", () => {
  const minimalInput = {
    pins: [],
    repoContent: null,
    userPrompt: "",
    presets: [],
  };

  it("always includes task, blueprint, copy guidelines, tech constraints, and output format", () => {
    const prompt = buildPrompt(minimalInput);
    expect(prompt).toContain("# Role & Task");
    expect(prompt).toContain("# Section Blueprint");
    expect(prompt).toContain("# Copy Guidelines");
    expect(prompt).toContain("# Technical Constraints");
    expect(prompt).toContain("# Output Format");
  });

  it("omits design configuration when no presets", () => {
    const prompt = buildPrompt(minimalInput);
    expect(prompt).not.toContain("# Design Configuration");
  });

  it("includes design configuration when presets are active", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      presets: [{ category: "Color", name: "Dark", value: "dark theme" }],
    });
    expect(prompt).toContain("# Design Configuration");
    expect(prompt).toContain("**Color:** Dark: dark theme");
  });

  it("includes pins when provided", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      pins: [{ url: "https://example.com", title: "Example", description: "A site" }],
    });
    expect(prompt).toContain("# Inspiration Sites");
    expect(prompt).toContain("https://example.com");
    expect(prompt).toContain("Example");
  });

  it("includes product info with stars when repo content provided", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      repoContent: {
        name: "my-tool",
        description: "A cool tool",
        readme: "# Features\n- Fast",
        language: "TypeScript",
        topics: ["cli", "dev"],
        stars: 1234,
        packageJson: JSON.stringify({ dependencies: { react: "^18" } }),
        fileTree: ["src/index.ts", "package.json"],
      },
    });
    expect(prompt).toContain("**Product:** my-tool");
    expect(prompt).toContain("**GitHub Stars:** 1,234");
    expect(prompt).toContain("# Tech Stack");
    expect(prompt).toContain("React");
    expect(prompt).toContain("# README Intelligence");
    expect(prompt).toContain("Features/Benefits");
    expect(prompt).toContain("Full README Reference");
  });

  it("omits stars line when stars is 0", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      repoContent: {
        name: "test",
        description: "",
        readme: "",
        language: "JS",
        topics: [],
        stars: 0,
        packageJson: "",
        fileTree: [],
      },
    });
    expect(prompt).not.toContain("GitHub Stars");
  });

  it("omits tech stack section when no deps and no file tree", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      repoContent: {
        name: "test",
        description: "",
        readme: "Hello",
        language: "JS",
        topics: [],
        stars: 0,
        packageJson: "",
        fileTree: [],
      },
    });
    expect(prompt).not.toContain("# Tech Stack");
  });

  it("includes user prompt in additional guidance", () => {
    const prompt = buildPrompt({
      ...minimalInput,
      userPrompt: "Make it dark themed with code snippets",
    });
    expect(prompt).toContain("# Additional Guidance");
    expect(prompt).toContain("dark themed with code snippets");
  });

  it("omits additional guidance when user prompt is empty", () => {
    const prompt = buildPrompt(minimalInput);
    expect(prompt).not.toContain("# Additional Guidance");
  });
});

// ---------------------------------------------------------------------------
// buildClaudePrompt — output format swap
// ---------------------------------------------------------------------------
describe("buildClaudePrompt", () => {
  it("replaces Gemini output format with Claude output format", () => {
    const result = buildClaudePrompt(
      { pins: [], repoContent: null, userPrompt: "", presets: [] },
      "/tmp/test-output"
    );
    expect(result).toContain("Write the landing page files directly");
    expect(result).not.toContain("Respond with ONLY a JSON object");
  });

  it("includes Claude system prefix with outputDir", () => {
    const result = buildClaudePrompt(
      { pins: [], repoContent: null, userPrompt: "", presets: [] },
      "/tmp/my-site"
    );
    expect(result).toContain("/tmp/my-site");
    expect(result).toContain("You are building a landing page");
  });
});
