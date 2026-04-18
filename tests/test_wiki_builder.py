"""Tests for wiki_builder.py — deterministic blueprint → markdown generator."""

import sys
from pathlib import Path

# Make archie/standalone importable — mirrors how consumer projects use .archie/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import json

import wiki_builder  # noqa: E402


def test_slugify_basic():
    assert wiki_builder.slugify("User Service") == "user-service"
    assert wiki_builder.slugify("PostgreSQL as primary store") == "postgresql-as-primary-store"
    assert wiki_builder.slugify("JWT over sessions") == "jwt-over-sessions"


def test_slugify_collision_suffix():
    seen: set[str] = set()
    a = wiki_builder.slugify_unique("User", seen)
    b = wiki_builder.slugify_unique("User", seen)
    c = wiki_builder.slugify_unique("User", seen)
    assert a == "user"
    assert b == "user-2"
    assert c == "user-3"


def test_slugify_strips_non_alnum():
    assert wiki_builder.slugify("Auth/Flow: v2!") == "auth-flow-v2"
    assert wiki_builder.slugify("   spaced   out   ") == "spaced-out"


def test_render_decision_page_basic():
    decision = {
        "title": "PostgreSQL as primary store",
        "chosen": "PostgreSQL 15",
        "rationale": "ACID guarantees for user data",
        "forced_by": "Compliance requirements",
        "enables": "Point-in-time recovery",
        "alternatives_rejected": ["MongoDB (no ACID)"],
    }
    md = wiki_builder.render_decision(decision, slug="postgresql-as-primary-store")
    assert md.startswith("---\n")
    assert "type: decision" in md
    assert "slug: postgresql-as-primary-store" in md
    assert "# PostgreSQL as primary store" in md
    assert "**Chosen:** PostgreSQL 15" in md
    assert "Compliance requirements" in md
    assert "MongoDB (no ACID)" in md


def test_render_decision_page_missing_optional_fields():
    decision = {
        "title": "Minimal decision",
        "chosen": "Option A",
    }
    md = wiki_builder.render_decision(decision, slug="minimal-decision")
    # Missing fields render as "N/A" or are omitted, but rendering must not crash
    assert "# Minimal decision" in md
    assert "**Chosen:** Option A" in md


def test_render_component_page_links_depends_on():
    component = {
        "name": "UserService",
        "purpose": "User auth and lifecycle",
        "depends_on": ["UserRepository"],
        "exposes_to": ["AuthController"],
    }
    component_slugs = {"UserService": "user-service", "UserRepository": "user-repository", "AuthController": "auth-controller"}
    md = wiki_builder.render_component(component, slug="user-service", component_slugs=component_slugs)
    assert "# UserService" in md
    assert "[UserRepository](../components/user-repository.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "User auth and lifecycle" in md


def test_render_component_page_handles_unknown_reference():
    component = {
        "name": "OrphanService",
        "purpose": "Depends on something not in the blueprint",
        "depends_on": ["ExternalThing"],
    }
    component_slugs = {"OrphanService": "orphan-service"}
    md = wiki_builder.render_component(component, slug="orphan-service", component_slugs=component_slugs)
    # Unknown references render as plain text, not broken links
    assert "ExternalThing" in md
    assert "[ExternalThing]" not in md


def test_render_pattern_page():
    pattern = {
        "name": "Repository",
        "when_to_use": "When abstracting data access",
        "when_not_to_use": "For trivial CRUD",
    }
    md = wiki_builder.render_pattern(pattern, slug="repository")
    assert "# Repository" in md
    assert "type: pattern" in md
    assert "When abstracting data access" in md
    assert "For trivial CRUD" in md


def test_render_pitfall_page_with_stems_from_link():
    pitfall = {
        "area": "Password storage",
        "description": "Plain text passwords",
        "stems_from": "PostgreSQL as primary store",
        "recommendation": "Hash with bcrypt",
    }
    decision_slugs = {"PostgreSQL as primary store": "postgresql-as-primary-store"}
    md = wiki_builder.render_pitfall(
        pitfall, slug="password-storage", decision_slugs=decision_slugs
    )
    assert "# Password storage" in md
    assert "Plain text passwords" in md
    assert "[PostgreSQL as primary store](../decisions/postgresql-as-primary-store.md)" in md
    assert "Hash with bcrypt" in md


def test_render_pitfall_page_with_unknown_stems_from():
    pitfall = {"area": "Foo", "description": "Bar", "stems_from": "UnknownDecision", "recommendation": "Fix"}
    md = wiki_builder.render_pitfall(pitfall, slug="foo", decision_slugs={})
    # Unknown stems_from still renders the prose
    assert "UnknownDecision" in md
    assert "[UnknownDecision]" not in md


def test_render_index():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {
            "PostgreSQL as primary store": "postgresql-as-primary-store",
            "JWT over sessions": "jwt-over-sessions",
        },
        "components": {
            "UserService": "user-service",
            "UserRepository": "user-repository",
            "AuthController": "auth-controller",
        },
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "# TestProject Wiki" in md
    assert "## Browse by type" in md
    assert "Decisions (2)" in md
    assert "Components (3)" in md
    assert "Patterns (1)" in md
    assert "Pitfalls (1)" in md
    # At least one link into a sub-page
    assert "[PostgreSQL as primary store](./decisions/postgresql-as-primary-store.md)" in md


def test_render_capability_page_links_all_relations():
    capability = {
        "name": "User Authentication",
        "purpose": "Users sign up, log in, and receive a JWT.",
        "entry_points": [
            "POST /api/auth/login -> AuthController.login",
            "screens/LoginScreen.tsx",
        ],
        "uses_components": ["UserService", "AuthController"],
        "constrained_by_decisions": ["JWT over sessions"],
        "related_pitfalls": ["Password storage"],
        "key_files": ["features/auth/**"],
        "evidence": ["features/auth/**"],
        "provenance": "INFERRED",
    }
    slugs = {
        "components": {"UserService": "user-service", "AuthController": "auth-controller"},
        "decisions": {"JWT over sessions": "jwt-over-sessions"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_capability(capability, slug="user-authentication", slugs=slugs)
    assert "type: capability" in md
    assert "provenance: INFERRED" in md
    assert "# User Authentication" in md
    assert "POST /api/auth/login -> AuthController.login" in md
    assert "[UserService](../components/user-service.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "[JWT over sessions](../decisions/jwt-over-sessions.md)" in md
    assert "[Password storage](../pitfalls/password-storage.md)" in md
    assert "features/auth/**" in md


def test_render_capability_tolerates_missing_fields():
    capability = {"name": "Minimal cap", "purpose": "Just a name"}
    md = wiki_builder.render_capability(
        capability, slug="minimal-cap", slugs={"components": {}, "decisions": {}, "pitfalls": {}}
    )
    assert "# Minimal cap" in md
    assert "type: capability" in md


def test_render_index_promotes_capabilities_at_top():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {"PostgreSQL as primary store": "postgresql-as-primary-store"},
        "components": {"UserService": "user-service"},
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
        "capabilities": {"User Authentication": "user-authentication"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "## Before you implement anything" in md
    # The capabilities section comes before the "Browse by type" section.
    before_idx = md.index("## Before you implement anything")
    browse_idx = md.index("## Browse by type")
    assert before_idx < browse_idx
    assert "[User Authentication](./capabilities/user-authentication.md)" in md
    assert "Capabilities (1)" in md


def test_as_text_handles_list():
    assert wiki_builder._as_text([]) == ""
    assert wiki_builder._as_text(["a", "b"]) == "a\nb"
    assert wiki_builder._as_text(["  spaced  ", "", "x"]) == "spaced\nx"


def test_as_text_handles_none_and_str():
    assert wiki_builder._as_text(None) == ""
    assert wiki_builder._as_text("  hello  ") == "hello"


def test_render_pitfall_handles_list_stems_from():
    pitfall = {
        "area": "Multi-upstream",
        "description": "Linked to 2 decisions",
        "stems_from": ["Decision A", "Decision B"],
        "recommendation": "Review",
    }
    decision_slugs = {"Decision A": "decision-a", "Decision B": "decision-b"}
    md = wiki_builder.render_pitfall(pitfall, slug="multi", decision_slugs=decision_slugs)
    assert "[Decision A](../decisions/decision-a.md)" in md
    assert "[Decision B](../decisions/decision-b.md)" in md


def test_render_pitfall_handles_empty_list_stems_from():
    pitfall = {
        "area": "No upstream",
        "description": "Standalone",
        "stems_from": [],
        "recommendation": "Fix",
    }
    md = wiki_builder.render_pitfall(pitfall, slug="no-up", decision_slugs={})
    assert "# No upstream" in md
    assert "Stems from" not in md  # Empty list produces no section
    assert "Fix" in md


def test_render_decision_handles_list_fields():
    """Wave 2 may emit forced_by/enables as list in some blueprints."""
    decision = {
        "title": "Decision with list fields",
        "chosen": "X",
        "forced_by": ["reason 1", "reason 2"],
        "enables": ["outcome 1"],
    }
    md = wiki_builder.render_decision(decision, slug="test")
    assert "reason 1" in md
    assert "reason 2" in md
    assert "outcome 1" in md


def test_extract_components_from_list():
    bp = {"components": [{"name": "A"}, {"name": "B"}]}
    assert wiki_builder._extract_components(bp) == [{"name": "A"}, {"name": "B"}]


def test_extract_components_from_nested_dict():
    """Real Archie output sometimes wraps components in a dict."""
    bp = {"components": {"structure_type": "layered", "components": [{"name": "X"}]}}
    assert wiki_builder._extract_components(bp) == [{"name": "X"}]


def test_extract_components_empty_or_missing():
    assert wiki_builder._extract_components({}) == []
    assert wiki_builder._extract_components({"components": None}) == []
    assert wiki_builder._extract_components({"components": "weird"}) == []


def test_render_index_uses_project_root_fallback_for_name(tmp_path):
    blueprint = {"decisions": {}, "components": [], "pitfalls": [], "capabilities": []}
    slug_map = {"decisions": {}, "components": {}, "patterns": {}, "pitfalls": {}, "capabilities": {}}
    md = wiki_builder.render_index(blueprint, slug_map, project_root=tmp_path)
    assert f"# {tmp_path.name} Wiki" in md


def test_render_pitfall_with_applies_to():
    pitfall = {
        "area": "Password storage",
        "description": "Storing plain-text passwords",
        "stems_from": "PostgreSQL as primary store",
        "recommendation": "Hash with bcrypt",
        "applies_to": ["features/auth/UserRepository.ts", "features/auth/PasswordHelper.ts"]
    }
    decision_slugs = {"PostgreSQL as primary store": "postgresql-as-primary-store"}
    md = wiki_builder.render_pitfall(pitfall, slug="password-storage", decision_slugs=decision_slugs)
    assert "# Password storage" in md
    assert "## Applies to" in md
    # Fenced code block for paths (grep-friendly)
    assert "```\nfeatures/auth/UserRepository.ts\nfeatures/auth/PasswordHelper.ts\n```" in md


def test_render_pitfall_without_applies_to_no_section():
    pitfall = {
        "area": "Some pitfall",
        "description": "desc",
        "recommendation": "fix it"
    }
    md = wiki_builder.render_pitfall(pitfall, slug="some-pitfall", decision_slugs={})
    assert "## Applies to" not in md


def test_render_pitfall_applies_to_empty_list_no_section():
    pitfall = {"area": "X", "description": "x", "applies_to": [], "recommendation": "x"}
    md = wiki_builder.render_pitfall(pitfall, slug="x", decision_slugs={})
    assert "## Applies to" not in md


def test_render_index_meta_project_name_takes_precedence(tmp_path):
    blueprint = {"meta": {"project_name": "ExplicitName"}}
    slug_map = {"decisions": {}, "components": {}, "patterns": {}, "pitfalls": {}, "capabilities": {}}
    md = wiki_builder.render_index(blueprint, slug_map, project_root=tmp_path)
    assert "# ExplicitName Wiki" in md
    assert f"# {tmp_path.name}" not in md


def test_render_guideline_full():
    guideline = {
        "name": "How to add a new auth-protected endpoint",
        "category": "Auth",
        "pattern_description": "Define the route in the Controller. Delegate to a Service method. Service calls Repository.",
        "libraries": ["express", "jsonwebtoken", "bcrypt"],
        "key_files": ["features/auth/AuthController.ts", "features/auth/UserService.ts"],
        "usage_example": "router.post('/api/protected', requireAuth, async (req, res) => { ... });",
        "tips": ["Always use the requireAuth middleware.", "Never call UserRepository from a Controller directly."]
    }
    md = wiki_builder.render_guideline(guideline, slug="how-to-add-a-new-auth-protected-endpoint")
    assert "type: guideline" in md
    assert "slug: how-to-add-a-new-auth-protected-endpoint" in md
    assert "category: Auth" in md
    assert "# How to add a new auth-protected endpoint" in md
    assert "**Category:** Auth" in md
    assert "## Pattern" in md
    assert "Define the route in the Controller" in md
    assert "## Libraries" in md
    assert "- express" in md
    assert "- jsonwebtoken" in md
    assert "## Key files" in md
    assert "`features/auth/AuthController.ts`" in md
    assert "## Usage example" in md
    assert "```" in md  # fenced code block
    assert "requireAuth" in md
    assert "## Tips" in md
    assert "- Always use the requireAuth middleware." in md


def test_render_guideline_minimal():
    """Only name + pattern_description present — other sections omitted."""
    guideline = {
        "name": "Tiny guideline",
        "pattern_description": "Just do X."
    }
    md = wiki_builder.render_guideline(guideline, slug="tiny-guideline")
    assert "# Tiny guideline" in md
    assert "## Pattern" in md
    assert "Just do X." in md
    assert "## Libraries" not in md
    assert "## Key files" not in md
    assert "## Usage example" not in md
    assert "## Tips" not in md


def test_render_architecture_rules_both_sections():
    blueprint = {
        "architecture_rules": {
            "file_placement_rules": [
                {"pattern": "HTTP controllers", "location": "features/<feature>/*Controller.ts", "rationale": "Feature-colocated"},
                {"pattern": "Services", "location": "features/<feature>/*Service.ts", "rationale": "Business logic isolation"},
            ],
            "naming_conventions": [
                {"applies_to": "Controller classes", "convention": "*Controller suffix, PascalCase", "example": "AuthController.ts"},
            ],
        }
    }
    md = wiki_builder.render_architecture_rules(blueprint)
    assert "# Architecture rules" in md
    assert "## File placement" in md
    assert "| Pattern | Location | Rationale |" in md
    assert "| HTTP controllers | `features/<feature>/*Controller.ts` | Feature-colocated |" in md
    assert "| Services | `features/<feature>/*Service.ts` |" in md
    assert "## Naming conventions" in md
    assert "| Applies to | Convention | Example |" in md
    assert "| Controller classes | *Controller suffix, PascalCase | `AuthController.ts` |" in md
    assert "type: rules-page" in md


def test_render_architecture_rules_only_file_placement():
    blueprint = {
        "architecture_rules": {
            "file_placement_rules": [
                {"pattern": "Tests", "location": "tests/", "rationale": "Co-located with features"},
            ],
        }
    }
    md = wiki_builder.render_architecture_rules(blueprint)
    assert "## File placement" in md
    assert "Tests" in md
    assert "## Naming conventions" not in md


def test_render_architecture_rules_empty_returns_empty():
    assert wiki_builder.render_architecture_rules({}) == ""
    assert wiki_builder.render_architecture_rules({"architecture_rules": {}}) == ""
    assert wiki_builder.render_architecture_rules({"architecture_rules": {"file_placement_rules": [], "naming_conventions": []}}) == ""


def test_render_development_rules_categorized():
    blueprint = {
        "development_rules": [
            {"category": "Security", "rule": "Never log passwords.", "rationale": "Logs get aggregated."},
            {"category": "Security", "rule": "Always use bcrypt.compare.", "rationale": "Timing-safe."},
            {"category": "Data access", "rule": "Services never touch DB directly.", "applies_to": ["features/**"]},
            {"rule": "Every async method returns Result<T, E>.", "rationale": "Uniform error surface."},
        ]
    }
    md = wiki_builder.render_development_rules(blueprint)
    assert "# Development rules" in md
    assert "## Security (2 rules)" in md
    assert "## Data access (1 rule)" in md
    assert "## Uncategorized rules (1 rule)" in md
    # Each rule appears with rationale where present
    assert "**Never log passwords.**" in md
    assert "Logs get aggregated." in md
    # applies_to rendered as code-formatted globs
    assert "`features/**`" in md
    # Security (2) appears before Data access (1) alphabetically? Or stable insertion order?
    # Implementation choice: keep insertion order for categories; rules within category also insertion order.
    security_idx = md.index("## Security")
    data_idx = md.index("## Data access")
    uncat_idx = md.index("## Uncategorized")
    assert security_idx < data_idx < uncat_idx


def test_render_development_rules_all_uncategorized():
    blueprint = {
        "development_rules": [
            {"rule": "Rule A."},
            {"rule": "Rule B."},
        ]
    }
    md = wiki_builder.render_development_rules(blueprint)
    assert "# Development rules" in md
    assert "## Uncategorized rules (2 rules)" in md
    # No other category headers
    assert "## Security" not in md


def test_render_development_rules_empty():
    assert wiki_builder.render_development_rules({}) == ""


def test_render_technology_full():
    blueprint = {
        "technology": {
            "stack": [
                {"category": "Language", "name": "TypeScript", "version": "5.3", "purpose": "Primary language"},
                {"category": "Runtime", "name": "Node.js", "version": "24 LTS", "purpose": "Server runtime"},
            ],
            "run_commands": {
                "dev": "npm run dev",
                "test": "npm test",
            },
        },
        "communication": {
            "integrations": [
                {"service": "PostgreSQL", "purpose": "Primary user store", "integration_point": "features/auth/UserRepository.ts"},
            ]
        }
    }
    md = wiki_builder.render_technology(blueprint)
    assert "# Technology" in md
    assert "## Stack" in md
    assert "| Category | Name | Version | Purpose |" in md
    assert "| Language | TypeScript | 5.3 | Primary language |" in md
    assert "## External integrations" in md
    assert "**PostgreSQL**" in md
    assert "features/auth/UserRepository.ts" in md
    assert "## Run commands" in md
    assert "npm run dev" in md
    assert "npm test" in md
    assert "type: technology" in md


def test_render_technology_only_stack():
    blueprint = {"technology": {"stack": [{"category": "Lang", "name": "Python", "version": "3.12"}]}}
    md = wiki_builder.render_technology(blueprint)
    assert "## Stack" in md
    assert "| Lang | Python | 3.12 |" in md
    assert "## External integrations" not in md
    assert "## Run commands" not in md


def test_render_technology_empty():
    assert wiki_builder.render_technology({}) == ""
    assert wiki_builder.render_technology({"technology": {}}) == ""
    assert wiki_builder.render_development_rules({"development_rules": []}) == ""


def test_render_quick_reference_full():
    blueprint = {
        "quick_reference": {
            "pattern_selection": [
                {"scenario": "New endpoint needs auth", "pattern": "requireAuth middleware + Service method"},
                {"scenario": "Validate password", "pattern": "bcrypt.compare in Service, never Repository"},
            ],
            "error_mapping": [
                {"error": "AuthError.InvalidCredentials", "status_code": 401, "solution": "Return JSON code 'invalid_credentials'"},
                {"error": "AuthError.UserExists", "status_code": 409, "solution": "Return JSON code 'user_exists'"},
            ],
        },
        "communication": {
            "pattern_selection_guide": [
                {"scenario": "Need a new HTTP endpoint", "recommended_pattern": "Controller → Service → Repository"},
                {"scenario": "Access the database", "recommended_pattern": "Always via Repository"},
            ]
        }
    }
    md = wiki_builder.render_quick_reference(blueprint)
    assert "# Quick reference" in md
    assert "## Which pattern should I use?" in md
    assert "| Scenario | Recommended pattern |" in md
    assert "| New endpoint needs auth | requireAuth middleware + Service method |" in md
    assert "## Pattern decision tree" in md
    assert "**Need a new HTTP endpoint**" in md
    assert "Controller \u2192 Service \u2192 Repository" in md
    assert "## Error handling" in md
    assert "| Error | Status code | Solution |" in md
    assert "| AuthError.InvalidCredentials | 401 | Return JSON code 'invalid_credentials' |" in md
    assert "type: quick-reference" in md


def test_render_quick_reference_partial():
    blueprint = {"quick_reference": {"error_mapping": [{"error": "E", "status_code": 500, "solution": "Retry"}]}}
    md = wiki_builder.render_quick_reference(blueprint)
    assert "## Error handling" in md
    assert "## Which pattern should I use?" not in md
    assert "## Pattern decision tree" not in md


def test_render_quick_reference_empty():
    assert wiki_builder.render_quick_reference({}) == ""
    assert wiki_builder.render_quick_reference({"quick_reference": {}}) == ""


def test_render_frontend_full():
    blueprint = {
        "frontend": {
            "framework": "Next.js 15 App Router",
            "state_management": "Zustand",
            "routing": "App Router file-based",
            "styling": "Tailwind CSS",
            "data_fetching": "React Query + Server Components",
            "rendering_strategy": "Mixed SSR + CSR",
            "conventions": "Page components in app/; client components explicitly marked 'use client'."
        }
    }
    md = wiki_builder.render_frontend(blueprint)
    assert "# Frontend" in md
    assert "**Framework:** Next.js 15 App Router" in md
    assert "**State management:** Zustand" in md
    assert "**Routing:** App Router file-based" in md
    assert "**Styling:** Tailwind CSS" in md
    assert "**Data fetching:** React Query + Server Components" in md
    assert "**Rendering strategy:** Mixed SSR + CSR" in md
    assert "## Conventions" in md
    assert "'use client'" in md
    assert "type: frontend" in md


def test_render_frontend_minimal():
    blueprint = {"frontend": {"framework": "React"}}
    md = wiki_builder.render_frontend(blueprint)
    assert "# Frontend" in md
    assert "**Framework:** React" in md
    assert "## Conventions" not in md


def test_render_frontend_empty_or_missing():
    assert wiki_builder.render_frontend({}) == ""
    assert wiki_builder.render_frontend({"frontend": {}}) == ""
    # All-empty string values should also skip.
    assert wiki_builder.render_frontend({"frontend": {"framework": "", "conventions": ""}}) == ""


def test_render_architecture_full():
    blueprint = {
        "meta": {
            "executive_summary": "TestProject is a small test-scope application. The primary flow is user authentication.",
            "architecture_style": "Layered MVC with repository pattern.",
        },
        "architecture_diagram": "graph TD\n  A[Controller] --> B[Service]\n  B --> C[Repository]",
    }
    md = wiki_builder.render_architecture(blueprint)
    assert "# Architecture" in md
    # Executive summary prose appears
    assert "TestProject is a small test-scope application" in md
    # Architecture style appears
    assert "## Architectural style" in md or "Layered MVC with repository pattern." in md
    # Mermaid fenced block present
    assert "## System diagram" in md
    assert "```mermaid" in md
    assert "graph TD" in md
    assert "A[Controller]" in md
    assert "type: architecture" in md


def test_render_architecture_only_diagram():
    blueprint = {"architecture_diagram": "graph LR\n  X --> Y"}
    md = wiki_builder.render_architecture(blueprint)
    assert "# Architecture" in md
    assert "```mermaid" in md
    assert "X --> Y" in md
    # No executive_summary content should appear
    assert "TestProject" not in md


def test_render_architecture_empty():
    assert wiki_builder.render_architecture({}) == ""
    assert wiki_builder.render_architecture({"architecture_diagram": ""}) == ""
    assert wiki_builder.render_architecture({"meta": {"executive_summary": "x"}}) != ""  # summary alone still renders


def test_render_component_full_enrichment():
    component = {
        "name": "UserService",
        "purpose": "User auth and lifecycle",
        "responsibility": "Owns user authentication and session lifecycle. Validates credentials via UserRepository, issues JWTs, handles password hashing.",
        "location": "features/auth/UserService.ts",
        "platform": "backend",
        "depends_on": ["UserRepository"],
        "exposes_to": ["AuthController"],
        "key_interfaces": [
            {"name": "login", "signature": "async login(email, password): Promise<Result<Session, AuthError>>", "description": "Validates credentials and issues a new JWT session."},
            {"name": "logout", "signature": "async logout(sessionId): Promise<void>", "description": "Invalidates a session server-side."}
        ],
        "key_files": [
            {"file": "features/auth/UserService.ts", "description": "Main implementation"},
            {"file": "features/auth/UserService.test.ts", "description": "Unit tests"}
        ]
    }
    component_slugs = {"UserService": "user-service", "UserRepository": "user-repository", "AuthController": "auth-controller"}
    md = wiki_builder.render_component(component, slug="user-service", component_slugs=component_slugs)

    assert "# UserService" in md
    assert "**Platform:** backend" in md
    assert "**Location:** `features/auth/UserService.ts`" in md
    assert "**Purpose:** User auth and lifecycle" in md
    # Responsibility section
    assert "## Responsibility" in md
    assert "Owns user authentication and session lifecycle" in md
    # depends_on / exposes_to still present (unchanged behavior)
    assert "[UserRepository](../components/user-repository.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    # Public interface
    assert "## Public interface" in md
    assert "**`login`**" in md
    assert "`async login(email, password): Promise<Result<Session, AuthError>>`" in md
    assert "Validates credentials and issues a new JWT session." in md
    assert "**`logout`**" in md
    # Key files
    assert "## Key files" in md
    assert "`features/auth/UserService.ts`" in md
    assert "Main implementation" in md


def test_render_component_only_legacy_fields_still_works():
    """Pre-enrichment fixture shape — only name/purpose/depends_on/exposes_to — must still render cleanly."""
    component = {
        "name": "LegacyComponent",
        "purpose": "Old-style component",
        "depends_on": ["OtherComponent"],
    }
    component_slugs = {"LegacyComponent": "legacy-component", "OtherComponent": "other-component"}
    md = wiki_builder.render_component(component, slug="legacy-component", component_slugs=component_slugs)
    assert "# LegacyComponent" in md
    assert "**Purpose:** Old-style component" in md
    assert "[OtherComponent](../components/other-component.md)" in md
    # New sections should NOT appear
    assert "## Responsibility" not in md
    assert "## Public interface" not in md
    assert "## Key files" not in md
    # Optional meta prefixes shouldn't appear either
    assert "**Platform:**" not in md
    assert "**Location:**" not in md


def test_render_component_platform_only():
    """If only platform is provided, show it without other meta prefixes."""
    component = {"name": "X", "platform": "ios"}
    md = wiki_builder.render_component(component, slug="x", component_slugs={"X": "x"})
    assert "**Platform:** ios" in md
    assert "**Location:**" not in md


def test_render_decisions_index_full():
    blueprint = {
        "decisions": {
            "architectural_style": {
                "chosen": "Layered MVC with repository pattern",
                "rationale": "Separation of concerns + testable data layer."
            },
            "trade_offs": [
                {"accepted_cost": "Token revocation harder", "gained_benefit": "Horizontal scalability"},
                {"accepted_cost": "Schema migrations need care", "gained_benefit": "Relational consistency"},
            ],
            "out_of_scope": ["OAuth social login", "Federated identity"],
            "key_decisions": [
                {"title": "PostgreSQL as primary store"},
                {"title": "JWT over sessions"},
            ],
        }
    }
    slug_map = {
        "decisions": {
            "PostgreSQL as primary store": "postgresql-as-primary-store",
            "JWT over sessions": "jwt-over-sessions",
        }
    }
    md = wiki_builder.render_decisions_index(blueprint, slug_map)
    assert "# Architectural decisions" in md
    assert "## Architectural style" in md
    assert "**Chosen:** Layered MVC with repository pattern" in md
    assert "**Rationale:** Separation of concerns" in md
    assert "## Trade-offs accepted" in md
    assert "| Accepted cost | Gained benefit |" in md
    assert "| Token revocation harder | Horizontal scalability |" in md
    assert "## Explicitly out of scope" in md
    assert "- OAuth social login" in md
    assert "- Federated identity" in md
    assert "## All decisions" in md
    assert "[PostgreSQL as primary store](./postgresql-as-primary-store.md)" in md
    assert "[JWT over sessions](./jwt-over-sessions.md)" in md
    assert "type: decisions-index" in md


def test_render_decisions_index_minimal():
    blueprint = {"decisions": {"key_decisions": [{"title": "Only one"}]}}
    slug_map = {"decisions": {"Only one": "only-one"}}
    md = wiki_builder.render_decisions_index(blueprint, slug_map)
    assert "# Architectural decisions" in md
    assert "## All decisions" in md
    assert "[Only one](./only-one.md)" in md
    # Empty sections omitted
    assert "## Architectural style" not in md
    assert "## Trade-offs accepted" not in md
    assert "## Explicitly out of scope" not in md


def test_render_decisions_index_empty():
    assert wiki_builder.render_decisions_index({}, {"decisions": {}}) == ""


def test_render_index_system_overview_section():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {"PostgreSQL as primary store": "postgresql-as-primary-store"},
        "components": {"UserService": "user-service"},
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
        "capabilities": {"User Authentication": "user-authentication"},
        "guidelines": {"How to add a new auth-protected endpoint": "how-to-add-a-new-auth-protected-endpoint"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    # System overview at top
    assert "## System overview" in md
    sys_idx = md.index("## System overview")
    before_idx = md.index("## Before you implement anything")
    assert sys_idx < before_idx
    # executive_summary from fixture appears
    assert "TestProject is a small test-scope application" in md
    # Architecture style
    assert "Layered MVC with repository pattern" in md
    # Platforms rendered as inline list
    assert "backend" in md


def test_render_index_has_browse_entries_for_new_page_types():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {"PostgreSQL as primary store": "postgresql-as-primary-store"},
        "components": {"UserService": "user-service"},
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
        "capabilities": {"User Authentication": "user-authentication"},
        "guidelines": {
            "How to add a new auth-protected endpoint": "how-to-add-a-new-auth-protected-endpoint",
            "How to hash a new password": "how-to-hash-a-new-password",
        },
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "## Browse by type" in md
    # New browse entries
    assert "Guidelines (2)" in md
    assert "Rules" in md  # 2 pages (arch + dev), listed as "Rules" row
    assert "Technology" in md
    assert "Quick reference" in md
    assert "Architecture" in md
    # Dedicated Guidelines section listing each
    assert "## Guidelines" in md
    assert "[How to add a new auth-protected endpoint](./guidelines/how-to-add-a-new-auth-protected-endpoint.md)" in md
    # Pointer to decisions overview in the decisions section
    assert "[Decisions overview](./decisions/index.md)" in md or "decisions/index.md" in md
