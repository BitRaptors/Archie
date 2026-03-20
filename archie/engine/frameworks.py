"""Detect frameworks from file entries and dependency entries."""
from __future__ import annotations

from .models import DependencyEntry, FileEntry, FrameworkSignal

# Maps a dependency name (or prefix) to a framework display name.
DEP_SIGNALS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "express": "Express",
    "nestjs": "NestJS",
    "gin": "Gin",
    "fiber": "Fiber",
    "actix-web": "Actix Web",
    "axum": "Axum",
    "rocket": "Rocket",
}

# Maps a filename to a framework display name.
FILE_SIGNALS: dict[str, str] = {
    "next.config.js": "Next.js",
    "next.config.ts": "Next.js",
    "next.config.mjs": "Next.js",
    "nuxt.config.ts": "Nuxt.js",
    "nuxt.config.js": "Nuxt.js",
    "svelte.config.js": "Svelte",
    "angular.json": "Angular",
    "manage.py": "Django",
    "pubspec.yaml": "Flutter",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "docker-compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
    "Dockerfile": "Docker",
    "tailwind.config.js": "Tailwind CSS",
    "tailwind.config.ts": "Tailwind CSS",
}

_DEP_BASE_CONFIDENCE = 0.9
_FILE_BASE_CONFIDENCE = 0.7
_EVIDENCE_BUMP = 0.1


def detect_frameworks(
    files: list[FileEntry],
    dependencies: list[DependencyEntry],
) -> list[FrameworkSignal]:
    """Return a sorted list of detected frameworks with confidence scores.

    Dependencies contribute a base confidence of 0.9, files contribute 0.7.
    Each additional piece of evidence bumps confidence by 0.1, capped at 1.0.
    """
    # Accumulate evidence per framework name.
    evidence_map: dict[str, list[str]] = {}
    confidence_map: dict[str, float] = {}
    version_map: dict[str, str] = {}

    # --- dependency signals ---
    for dep in dependencies:
        framework = DEP_SIGNALS.get(dep.name)
        if framework is None:
            continue
        if framework not in evidence_map:
            evidence_map[framework] = []
            confidence_map[framework] = _DEP_BASE_CONFIDENCE
        else:
            confidence_map[framework] = min(
                confidence_map[framework] + _EVIDENCE_BUMP, 1.0
            )
        evidence_map[framework].append(f"dependency:{dep.name}")
        if dep.version and not version_map.get(framework):
            version_map[framework] = dep.version

    # --- file signals ---
    for fe in files:
        # Match on the basename (last component of the path).
        basename = fe.path.rsplit("/", 1)[-1] if "/" in fe.path else fe.path
        framework = FILE_SIGNALS.get(basename)
        if framework is None:
            continue
        if framework not in evidence_map:
            evidence_map[framework] = []
            confidence_map[framework] = _FILE_BASE_CONFIDENCE
        else:
            confidence_map[framework] = min(
                confidence_map[framework] + _EVIDENCE_BUMP, 1.0
            )
        evidence_map[framework].append(f"file:{fe.path}")

    # Build result list sorted by confidence descending, then name ascending.
    signals: list[FrameworkSignal] = []
    for name in evidence_map:
        signals.append(
            FrameworkSignal(
                name=name,
                version=version_map.get(name, ""),
                confidence=confidence_map[name],
                evidence=evidence_map[name],
            )
        )

    signals.sort(key=lambda s: (-s.confidence, s.name))
    return signals
