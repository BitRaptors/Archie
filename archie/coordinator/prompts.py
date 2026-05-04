"""Prompt builders for the coordinator (Opus) and subagents (Sonnet)."""
from __future__ import annotations


from archie.coordinator.planner import SubagentAssignment
from archie.engine.models import RawScan

# ---------------------------------------------------------------------------
# Complete JSON schema example for the StructuredBlueprint
# ---------------------------------------------------------------------------
_BLUEPRINT_SCHEMA_EXAMPLE = r"""
{
  "meta": {
    "executive_summary": "3-5 factual sentences describing what this codebase does, its scale, and key technologies",
    "platforms": ["backend", "web-frontend"],
    "confidence": {
      "architecture_rules": 0.9,
      "decisions": 0.85,
      "components": 0.9,
      "communication": 0.8,
      "technology": 0.95,
      "frontend": 0.0,
      "deployment": 0.7
    }
  },
  "architecture_rules": {
    "file_placement_rules": [
      {
        "component_type": "API endpoint",
        "naming_pattern": "*_controller.py",
        "location": "src/controllers/",
        "example": "src/controllers/user_controller.py",
        "description": "All API endpoint handlers go in src/controllers/"
      }
    ],
    "naming_conventions": [
      {
        "scope": "files",
        "pattern": "snake_case",
        "examples": ["user_service.py", "auth_controller.py"],
        "description": "All Python files use snake_case naming"
      }
    ]
  },
  "decisions": {
    "architectural_style": {
      "title": "Clean Architecture",
      "chosen": "Layered Clean Architecture with DDD",
      "rationale": "Enables swapping infrastructure without changing business logic",
      "alternatives_rejected": ["Microservices — too complex for team size", "Simple MVC — insufficient separation"]
    },
    "key_decisions": [
      {
        "title": "Database choice",
        "chosen": "PostgreSQL with pgvector",
        "rationale": "Supports both relational data and vector embeddings",
        "alternatives_rejected": ["MongoDB — no native vector support", "SQLite — no concurrent writes"]
      }
    ],
    "trade_offs": [
      {"accept": "Slower startup time", "benefit": "Full type safety at compile time"}
    ],
    "out_of_scope": ["Multi-tenant support", "Real-time collaboration"]
  },
  "components": {
    "structure_type": "layered",
    "components": [
      {
        "name": "API Layer",
        "location": "src/api/",
        "responsibility": "Expose HTTP endpoints, validate requests, transform DTOs",
        "platform": "backend",
        "depends_on": ["Application Services"],
        "exposes_to": ["Frontend", "External Clients"],
        "key_interfaces": [
          {"name": "UserController", "methods": ["getUser", "createUser"], "description": "User CRUD operations"}
        ],
        "key_files": [
          {"path": "src/api/user.py", "purpose": "User endpoints"},
          {"path": "src/api/auth.py", "purpose": "Authentication endpoints"}
        ]
      }
    ],
    "contracts": [
      {
        "interface_name": "IRepository",
        "description": "Generic CRUD interface for persistence",
        "methods": ["get", "create", "update", "delete"],
        "properties": [],
        "implementing_files": ["src/repos/user_repo.py"]
      }
    ]
  },
  "communication": {
    "patterns": [
      {
        "name": "REST API",
        "when_to_use": "Client-server communication",
        "how_it_works": "JSON over HTTP with resource-based URLs",
        "examples": ["GET /api/users", "POST /api/orders"],
        "applicable_when": "",
        "do_not_apply_when": [],
        "scope": []
      }
    ],
    "integrations": [
      {"service": "Stripe", "purpose": "Payment processing", "integration_point": "src/services/payment.py"}
    ],
    "pattern_selection_guide": [
      {"scenario": "Need real-time updates", "pattern": "WebSocket", "rationale": "Lower latency than polling"}
    ]
  },
  "quick_reference": {
    "where_to_put_code": {
      "new API endpoint": "src/api/routes/",
      "new business logic": "src/services/",
      "new database model": "src/models/"
    },
    "pattern_selection": [
      {"scenario": "long-running task", "pattern": "Background job via worker queue", "scope": []},
      {"scenario": "real-time update", "pattern": "WebSocket or SSE", "scope": []},
      {"scenario": "concurrent mutation of a single entity row", "pattern": "Per-key advisory lock inside transaction", "scope": ["<domain-A>", "<domain-B>"]}
    ],
    "error_mapping": [
      {"error": "NotFoundError", "status_code": 404, "description": "Resource does not exist"}
    ]
  },
  "technology": {
    "stack": [
      {"category": "runtime", "name": "Python", "version": "3.11", "purpose": "Primary backend language"},
      {"category": "framework", "name": "FastAPI", "version": "0.110", "purpose": "HTTP framework"},
      {"category": "database", "name": "PostgreSQL", "version": "15", "purpose": "Primary data store"}
    ],
    "templates": [
      {
        "component_type": "API endpoint",
        "description": "Standard REST endpoint with dependency injection",
        "file_path_template": "src/api/{resource}.py",
        "code": "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/{resource}')\nasync def list():..."
      }
    ],
    "project_structure": "src/\n├── api/\n│   ├── routes/\n│   └── middleware/\n├── services/\n├── models/\n└── config/",
    "run_commands": {"dev": "uvicorn main:app --reload", "test": "pytest", "lint": "ruff check ."}
  },
  "frontend": {
    "framework": "Next.js 15",
    "rendering_strategy": "SSR with App Router",
    "ui_components": [
      {
        "name": "Header",
        "location": "src/components/Header.tsx",
        "component_type": "layout",
        "description": "App header with navigation",
        "props": ["user", "onLogout"],
        "children": ["NavMenu", "UserAvatar"]
      }
    ],
    "state_management": {
      "approach": "React Query + Context",
      "global_state": [{"store": "AuthContext", "purpose": "User session"}],
      "server_state": "TanStack Query",
      "local_state": "useState",
      "rationale": "Minimal boilerplate for data-driven app"
    },
    "routing": [
      {"path": "/", "component": "HomePage", "description": "Dashboard", "auth_required": true},
      {"path": "/login", "component": "LoginPage", "description": "Authentication", "auth_required": false}
    ],
    "data_fetching": [
      {
        "name": "useUsers",
        "mechanism": "React Query hook",
        "when_to_use": "Display user list",
        "examples": ["const { data } = useUsers()"]
      }
    ],
    "styling": "Tailwind CSS 4 with custom design tokens",
    "key_conventions": ["'use client' directive on all interactive components", "co-locate hooks with their consuming components"]
  },
  "developer_recipes": [
    {
      "task": "Add a new API endpoint",
      "files": ["src/api/routes/new.py", "src/services/new_service.py"],
      "steps": ["Create route file in src/api/routes/", "Add service logic in src/services/", "Register route in app.py", "Add tests"]
    }
  ],
  "architecture_diagram": "graph TD\n  Client --> API\n  API --> Services\n  Services --> DB",
  "pitfalls": [
    {"area": "Database", "description": "SQLite has no concurrent write support", "recommendation": "Use WAL mode or queue writes"}
  ],
  "implementation_guidelines": [
    {
      "capability": "Authentication",
      "category": "auth",
      "libraries": ["next-auth 5.0"],
      "pattern_description": "Session-based auth with JWT tokens stored in httpOnly cookies",
      "key_files": ["src/lib/auth.ts", "src/middleware.ts"],
      "usage_example": "const session = await getServerSession(authOptions)",
      "applicable_when": "src/app/layout.tsx wraps the entire tree in <SessionProvider> — useSession() is therefore safe to call from any descendant client component",
      "do_not_apply_when": ["Caller is a server component or middleware — context is unavailable there; getServerSession() is the correct API", "Component renders in test isolation without SessionProvider — context is null and the hook throws"],
      "scope": [],
      "tips": ["Always check session in middleware, not in individual routes"]
    }
  ],
  "development_rules": [
    {"category": "code_style", "rule": "Always use TypeScript strict mode", "source": "tsconfig.json strict: true"}
  ],
  "deployment": {
    "runtime_environment": "Vercel",
    "compute_services": ["Vercel Serverless Functions"],
    "container_runtime": "",
    "orchestration": "",
    "serverless_functions": "",
    "ci_cd": ["GitHub Actions", "Vercel CI"],
    "distribution": ["Web (vercel.app)"],
    "infrastructure_as_code": "",
    "supporting_services": ["Supabase"],
    "environment_config": ".env.local with NEXT_PUBLIC_ prefix for client vars",
    "key_files": ["vercel.json", ".github/workflows/ci.yml"]
  }
}
""".strip()

# ---------------------------------------------------------------------------
# Schema guidance snippets for each blueprint section — now with full
# field-level specificity matching the StructuredBlueprint Pydantic model
# ---------------------------------------------------------------------------
_SECTION_GUIDANCE: dict[str, str] = {
    "components": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"structure_type\": one of \"layered\", \"modular\", \"feature-based\", \"flat\", or \"other\"\n"
        "- \"components\": array of objects, each with ALL of these fields:\n"
        "    - \"name\": string — component/layer name (e.g. \"API Layer\", \"Domain Services\")\n"
        "    - \"location\": string — directory path (e.g. \"src/api/\")\n"
        "    - \"responsibility\": string — what this component does (1-2 sentences)\n"
        "    - \"platform\": one of \"backend\", \"frontend\", \"shared\", or \"\"\n"
        "    - \"depends_on\": array of component names this depends on\n"
        "    - \"exposes_to\": array of component/consumer names this exposes to\n"
        "    - \"key_interfaces\": array of {\"name\": str, \"methods\": [str], \"description\": str}\n"
        "    - \"key_files\": array of {\"path\": str, \"purpose\": str}\n"
        "- \"contracts\": array of interface contracts between components, each with:\n"
        "    - \"interface_name\": str, \"description\": str, \"methods\": [str],\n"
        "      \"properties\": [str], \"implementing_files\": [str]\n"
        "\n"
        "Example component:\n"
        "```json\n"
        "{\n"
        "  \"name\": \"API Layer\",\n"
        "  \"location\": \"src/api/\",\n"
        "  \"responsibility\": \"Expose HTTP endpoints, validate requests, transform DTOs\",\n"
        "  \"platform\": \"backend\",\n"
        "  \"depends_on\": [\"Application Services\"],\n"
        "  \"exposes_to\": [\"Frontend\", \"External Clients\"],\n"
        "  \"key_interfaces\": [{\"name\": \"UserController\", \"methods\": [\"getUser\", \"createUser\"], \"description\": \"User CRUD\"}],\n"
        "  \"key_files\": [{\"path\": \"src/api/user.py\", \"purpose\": \"User endpoints\"}]\n"
        "}\n"
        "```"
    ),
    "architecture_rules": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"file_placement_rules\": array of objects, each with ALL of:\n"
        "    - \"component_type\": str — what kind of code (e.g. \"API endpoint\", \"Service\", \"Model\")\n"
        "    - \"naming_pattern\": str — glob pattern (e.g. \"*_controller.py\", \"*.service.ts\")\n"
        "    - \"location\": str — directory path (e.g. \"src/controllers/\")\n"
        "    - \"example\": str — concrete file path (e.g. \"src/controllers/user_controller.py\")\n"
        "    - \"description\": str — human-readable rule\n"
        "- \"naming_conventions\": array of objects, each with ALL of:\n"
        "    - \"scope\": one of \"classes\", \"functions\", \"files\", \"modules\", \"variables\"\n"
        "    - \"pattern\": str — the naming pattern (e.g. \"snake_case\", \"PascalCase\", \"camelCase\")\n"
        "    - \"examples\": array of concrete example names\n"
        "    - \"description\": str — human-readable description\n"
        "\n"
        "Example:\n"
        "```json\n"
        "{\n"
        "  \"file_placement_rules\": [{\"component_type\": \"API endpoint\", \"naming_pattern\": \"*_controller.py\", \"location\": \"src/controllers/\", \"example\": \"src/controllers/user_controller.py\", \"description\": \"All endpoint handlers\"}],\n"
        "  \"naming_conventions\": [{\"scope\": \"files\", \"pattern\": \"snake_case\", \"examples\": [\"user_service.py\"], \"description\": \"Python files use snake_case\"}]\n"
        "}\n"
        "```"
    ),
    "decisions": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"architectural_style\": object with ALL of:\n"
        "    - \"title\": str — name of the style\n"
        "    - \"chosen\": str — specific variant chosen\n"
        "    - \"rationale\": str — why this was chosen\n"
        "    - \"alternatives_rejected\": array of strings (each: \"Alternative — reason rejected\")\n"
        "- \"key_decisions\": array of objects, each with ALL of:\n"
        "    - \"title\": str, \"chosen\": str, \"rationale\": str, \"alternatives_rejected\": [str]\n"
        "- \"trade_offs\": array of {\"accept\": str, \"benefit\": str}\n"
        "- \"out_of_scope\": array of strings describing what the codebase explicitly does NOT do\n"
        "\n"
        "Example key_decision:\n"
        "```json\n"
        "{\"title\": \"Database choice\", \"chosen\": \"PostgreSQL\", \"rationale\": \"Relational + vector support\", \"alternatives_rejected\": [\"MongoDB — no native vector support\"]}\n"
        "```"
    ),
    "communication": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"patterns\": array of objects, each with ALL of:\n"
        "    - \"name\": str (e.g. \"REST API\", \"WebSocket\", \"Event Bus\")\n"
        "    - \"when_to_use\": str — scenario description\n"
        "    - \"how_it_works\": str — technical description\n"
        "    - \"examples\": array of concrete usage strings (e.g. \"GET /api/users\")\n"
        "    - \"applicable_when\": str — the verifiable invariant that makes this pattern correct.\n"
        "        MUST cite a code artifact (schema annotation, type signature, struct tag, structural invariant).\n"
        "        NOT prose like \"per-customer operations\" — those pattern-match too easily across domains.\n"
        "        Empty string (\"\") if no schema/code-level invariant applies (e.g. for generic patterns like REST).\n"
        "        REQUIRED SHAPE — category-then-evidence: the predicate must name the CLASS of\n"
        "        callers/situations the invariant guards (a categorical noun phrase a future agent\n"
        "        can pattern-match against an unfamiliar component); the citation grounds that\n"
        "        category by showing where the invariant is declared. Substitution test: if you can\n"
        "        swap any other component name into the predicate and the sentence still parses, the\n"
        "        shape is right. If it only makes sense about ONE specific file, you wrote trivia.\n"
        "        BAD: \"BabyWeatherAnalyticsManager uses an internal AtomicBoolean singleton and its own\n"
        "        initialize() — exposed through analyticsModule but not constructed via Koin injection.\"\n"
        "        (true, falsifiable, useless — predicate names a single entity, not a class of cases).\n"
        "        GOOD: \"Component manages its own initialization lifecycle (manual initialize() outside\n"
        "        DI; Koin only exposes the already-built instance) — BabyWeatherAnalyticsManager\n"
        "        (analyticsModule), LocalisationHelper (DomainModules.kt:18-21).\" (predicate is a class\n"
        "        of cases; citations are evidence the class exists in the corpus.)\n"
        "    - \"do_not_apply_when\": array of strings — concrete anti-indicators (each citable against code),\n"
        "        each following the SAME category-then-evidence shape as applicable_when. Lead with a\n"
        "        categorical noun phrase describing the kind of caller/context where the pattern misapplies,\n"
        "        then cite. Reject per-file descriptions with a citation tacked on.\n"
        "        Examples of contexts in the corpus where this shape would silently break.\n"
        "        Empty array if the pattern is universally safe.\n"
        "    - \"scope\": array of strings — component names from components.components[].name where this\n"
        "        pattern legitimately applies. Empty array means \"applies repo-wide\".\n"
        "- \"integrations\": array of {\"service\": str, \"purpose\": str, \"integration_point\": str}\n"
        "- \"pattern_selection_guide\": array of {\"scenario\": str, \"pattern\": str, \"rationale\": str}\n"
        "\n"
        "Example pattern (generic — empty invariant fields):\n"
        "```json\n"
        "{\"name\": \"REST API\", \"when_to_use\": \"Client-server communication\", \"how_it_works\": \"JSON over HTTP\", \"examples\": [\"GET /api/users\"], \"applicable_when\": \"\", \"do_not_apply_when\": [], \"scope\": []}\n"
        "```\n"
        "\n"
        "Example pattern (invariant-bound — fields populated; placeholder paths shown to keep this\n"
        "language-agnostic — substitute the actual files for the codebase you are analyzing):\n"
        "```json\n"
        "{\"name\": \"Per-key advisory lock\", \"when_to_use\": \"Serialize concurrent mutations of the same logical entity\", \"how_it_works\": \"Acquire a database advisory lock keyed on (namespace, entityID) inside a transaction; lock auto-releases on commit/rollback\", \"examples\": [\"<lib>/lock.<ext>\", \"<domain>/service/write.<ext>\"], \"applicable_when\": \"<schema>/<entity>.<ext>:<line> declares a UNIQUE index on the lock-key columns — (namespace, entityID) maps to at most one row\", \"do_not_apply_when\": [\"Schema index for the proposed key is NOT unique — multiple rows can share the key, so a single lock would serialize unrelated rows\"], \"scope\": [\"<domain-A>\", \"<domain-B>\"]}\n"
        "```"
    ),
    "technology": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"stack\": array of objects, each with ALL of:\n"
        "    - \"category\": one of \"runtime\", \"framework\", \"database\", \"cache\", \"queue\", \"ai\", \"auth\", \"testing\", or other\n"
        "    - \"name\": str — technology name\n"
        "    - \"version\": str — version string (or \"\" if unknown)\n"
        "    - \"purpose\": str — why it is used\n"
        "- \"templates\": array of code templates, each with ALL of:\n"
        "    - \"component_type\": str — what this template creates\n"
        "    - \"description\": str — what the template does\n"
        "    - \"file_path_template\": str — path pattern with {placeholders}\n"
        "    - \"code\": str — actual code sample showing the boilerplate pattern\n"
        "- \"project_structure\": string — ASCII directory tree of the project layout\n"
        "- \"run_commands\": dict mapping command names to commands, e.g. {\"dev\": \"uvicorn main:app --reload\", \"test\": \"pytest\"}\n"
        "\n"
        "Example template:\n"
        "```json\n"
        "{\"component_type\": \"API endpoint\", \"description\": \"Standard REST endpoint\", \"file_path_template\": \"src/api/{resource}.py\", \"code\": \"from fastapi import APIRouter\\nrouter = APIRouter()\\n@router.get('/{resource}')\\nasync def list():...\"}\n"
        "```\n"
        "\n"
        "For project_structure, produce an ASCII tree like:\n"
        "src/\n"
        "├── api/\n"
        "│   ├── routes/\n"
        "│   └── middleware/\n"
        "├── services/\n"
        "└── models/"
    ),
    "frontend": (
        "If the codebase has frontend code, you MUST fill ALL of these fields:\n"
        "- \"framework\": str — e.g. \"Next.js 15\", \"React Native 0.73\", \"Vue 3\"\n"
        "- \"rendering_strategy\": one of \"SSR\", \"SSG\", \"CSR\", \"ISR\", \"hybrid\", or description\n"
        "- \"ui_components\": array of objects, each with ALL of:\n"
        "    - \"name\": str, \"location\": str (file path), \"component_type\": one of \"page\", \"layout\", \"feature\", \"shared\", \"primitive\"\n"
        "    - \"description\": str, \"props\": [str] (prop names), \"children\": [str] (child component names)\n"
        "- \"state_management\": object with ALL of:\n"
        "    - \"approach\": str (e.g. \"React Query + Context\", \"Redux Toolkit\")\n"
        "    - \"global_state\": array of {\"store\": str, \"purpose\": str}\n"
        "    - \"server_state\": str (e.g. \"TanStack Query\", \"SWR\")\n"
        "    - \"local_state\": str (e.g. \"useState\", \"useReducer\")\n"
        "    - \"rationale\": str — why this approach was chosen\n"
        "- \"routing\": array of {\"path\": str, \"component\": str, \"description\": str, \"auth_required\": bool}\n"
        "- \"data_fetching\": array of objects with ALL of:\n"
        "    - \"name\": str, \"mechanism\": str (e.g. \"React Query hook\", \"fetch in loader\")\n"
        "    - \"when_to_use\": str, \"examples\": [str] (code usage examples)\n"
        "- \"styling\": str — e.g. \"Tailwind CSS 4\", \"CSS Modules\", \"Styled Components\"\n"
        "- \"key_conventions\": array of strings describing frontend conventions\n"
        "\n"
        "If NO frontend code exists, return an empty object {}.\n"
        "\n"
        "Example ui_component:\n"
        "```json\n"
        "{\"name\": \"Header\", \"location\": \"src/components/Header.tsx\", \"component_type\": \"layout\", \"description\": \"App header with nav\", \"props\": [\"user\", \"onLogout\"], \"children\": [\"NavMenu\", \"UserAvatar\"]}\n"
        "```"
    ),
    "implementation_guidelines": (
        "You MUST return an array of objects, each with ALL of:\n"
        "- \"capability\": str — what was implemented (e.g. \"Authentication\", \"Push Notifications\")\n"
        "- \"category\": str — one of \"auth\", \"notifications\", \"location\", \"media\", \"persistence\", \"ui\", or other\n"
        "- \"libraries\": array of strings (library name + version, e.g. [\"next-auth 5.0\"])\n"
        "- \"pattern_description\": str — 1-3 sentences on how it was built\n"
        "- \"key_files\": array of actual file paths involved\n"
        "- \"usage_example\": str — code snippet or invocation pattern\n"
        "- \"applicable_when\": str — the verifiable invariant that makes this pattern correct in THIS\n"
        "    codebase. MUST cite a concrete code artifact at <file>:<line>. The shape of the citation\n"
        "    varies by language and paradigm; the requirement is that it be falsifiable against the\n"
        "    corpus, not free-form prose. Common shapes:\n"
        "      • Schema annotation: a unique/foreign-key/NOT-NULL/index constraint the pattern relies on\n"
        "      • Type signature: a function returning Result/Option/Either; an exhaustive enum or sealed type;\n"
        "        a generic bound that constrains callers\n"
        "      • Lifecycle / framework state: a hook/effect called under a required Provider; a handler\n"
        "        registered before bus start; a composable inside a known scope\n"
        "      • Ownership / concurrency: a borrow scope, a held-lock interval, a transaction-active context\n"
        "      • Structural: a single registration point + an iterating consumer; a sealed hierarchy +\n"
        "        an exhaustive match; a conventional placement enforced by build/lint config\n"
        "    Do NOT use prose like \"per-customer\" or \"in the auth flow\" — those pattern-match across\n"
        "    contexts where the invariant doesn't hold. If you cannot cite a code artifact, leave empty (\"\").\n"
        "    REQUIRED SHAPE — category-then-evidence: the predicate must name the CLASS of\n"
        "    callers/situations the invariant guards (substitutable across components — if the predicate\n"
        "    only makes sense about ONE specific file, you wrote trivia). Then back it with the\n"
        "    <file>:<line> citation as evidence the class exists in the corpus.\n"
        "    BAD: \"BabyWeatherAnalyticsManager uses an internal AtomicBoolean singleton and its own\n"
        "    initialize() — exposed through analyticsModule but not constructed via Koin injection.\"\n"
        "    (one-file fact, no class of cases to match against).\n"
        "    GOOD: \"Component manages its own initialization lifecycle (manual initialize() outside DI;\n"
        "    Koin only exposes the already-built instance) — BabyWeatherAnalyticsManager (analyticsModule),\n"
        "    LocalisationHelper (DomainModules.kt:18-21).\" (named class of cases + citations as evidence.)\n"
        "- \"do_not_apply_when\": array of strings — concrete anti-indicators (each citable against code)\n"
        "    and each following the SAME category-then-evidence shape as applicable_when: a categorical\n"
        "    noun phrase + citation, never a per-file description.\n"
        "    Cases visible in the corpus where this pattern's shape is used WITHOUT the invariant holding,\n"
        "    or contexts where applying it would silently break. Empty array if universally safe.\n"
        "- \"scope\": array of strings — component names from components.components[].name where this\n"
        "    pattern is RELEVANT WHEN EDITING (producers, consumers, boundary participants — not just\n"
        "    where the source file lives). Empty array means \"applies repo-wide\". The renderer translates\n"
        "    non-empty scope into rule-file globs so out-of-scope edits never load the entry.\n"
        "    Conservative default: leave empty unless there is verifiable evidence the pattern is\n"
        "    component-bound (no regression vs. today).\n"
        "- \"tips\": array of gotcha strings for this capability\n"
        "\n"
        "Two illustrative examples — each grounds applicable_when in a different invariant shape, to\n"
        "show that the field is paradigm-agnostic. Pick whichever shape fits the codebase you are\n"
        "analyzing; do not force a schema annotation if the codebase has none.\n"
        "\n"
        "Example A (lifecycle / framework state — typical for UI codebases):\n"
        "```json\n"
        "{\"capability\": \"Auth session via context hook\", \"category\": \"auth\",\n"
        " \"libraries\": [\"<framework>@<version>\"],\n"
        " \"pattern_description\": \"useSession() reads from a context populated by SessionProvider; provider hydrates from cookie on mount.\",\n"
        " \"key_files\": [\"src/auth/provider.<ext>\", \"src/auth/use-session.<ext>\"],\n"
        " \"usage_example\": \"const { user } = useSession()\",\n"
        " \"applicable_when\": \"src/app/layout.<ext>:14 wraps the entire tree in <SessionProvider> — the hook is therefore safe to call from any descendant.\",\n"
        " \"do_not_apply_when\": [\"Caller is a server component or middleware — context is unavailable; the server-side equivalent (e.g. getServerSession) is the correct API\", \"Test renders the component in isolation without SessionProvider — context is null and the hook throws\"],\n"
        " \"scope\": [],\n"
        " \"tips\": [\"Provider must be the outermost wrapper; nesting it under Suspense causes hydration mismatches.\"]}\n"
        "```\n"
        "\n"
        "Example B (schema-bound — typical for DB-backed services):\n"
        "```json\n"
        "{\"capability\": \"Per-key serialization for write paths\", \"category\": \"persistence\",\n"
        " \"libraries\": [\"<advisory-lock-lib>\"],\n"
        " \"pattern_description\": \"Acquire a per-row advisory lock keyed on (namespace, entityID) inside a transaction before mutating the entity.\",\n"
        " \"key_files\": [\"<lib>/lock.<ext>\", \"<domain>/service/write.<ext>\"],\n"
        " \"usage_example\": \"locker.Acquire(ctx, key); /* mutate; commit releases */\",\n"
        " \"applicable_when\": \"<schema>/<entity>.<ext>:<line> declares a UNIQUE index on the lock-key columns — (namespace, entityID) maps to at most one row.\",\n"
        " \"do_not_apply_when\": [\"Schema index for the proposed key is NOT unique — multiple rows can legitimately share the key, so a single advisory lock would serialize unrelated rows\", \"Operation mutates one row only — built-in row-level locking (e.g. SELECT FOR UPDATE) suffices, no cross-row invariant to protect\"],\n"
        " \"scope\": [\"<domain-A>\", \"<domain-B>\"],\n"
        " \"tips\": [\"Lock must be inside an active transaction — auto-released on commit/rollback.\"]}\n"
        "```"
    ),
    "deployment": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"runtime_environment\": str — e.g. \"AWS\", \"Google Cloud Platform\", \"Vercel\", \"self-hosted\"\n"
        "- \"compute_services\": array of strings — e.g. [\"Cloud Run\", \"Lambda\", \"Vercel Serverless\"]\n"
        "- \"container_runtime\": str — \"Docker\", \"Podman\", or \"\"\n"
        "- \"orchestration\": str — \"Kubernetes\", \"Docker Compose\", \"ECS\", or \"\"\n"
        "- \"serverless_functions\": str — \"Cloud Functions\", \"Lambda\", or \"\"\n"
        "- \"ci_cd\": array of strings — e.g. [\"GitHub Actions\", \"Cloud Build\"]\n"
        "- \"distribution\": array of strings — e.g. [\"App Store\", \"npm registry\", \"Docker Hub\"]\n"
        "- \"infrastructure_as_code\": str — \"Terraform\", \"CloudFormation\", or \"\"\n"
        "- \"supporting_services\": array of strings — e.g. [\"Supabase\", \"Redis Cloud\"]\n"
        "- \"environment_config\": str — how env vars are managed\n"
        "- \"key_files\": array of deployment-related file paths\n"
        "\n"
        "Example:\n"
        "```json\n"
        "{\"runtime_environment\": \"Vercel\", \"compute_services\": [\"Vercel Serverless Functions\"], \"container_runtime\": \"\", \"orchestration\": \"\", \"serverless_functions\": \"\", \"ci_cd\": [\"GitHub Actions\"], \"distribution\": [\"Web (vercel.app)\"], \"infrastructure_as_code\": \"\", \"supporting_services\": [\"Supabase\"], \"environment_config\": \".env.local\", \"key_files\": [\"vercel.json\"]}\n"
        "```"
    ),
    "developer_recipes": (
        "You MUST return an array of objects, each with ALL of:\n"
        "- \"task\": str — what the developer wants to do (e.g. \"Add a new API endpoint\")\n"
        "- \"files\": array of file paths that need to be touched\n"
        "- \"steps\": array of step-by-step instructions as strings\n"
        "\n"
        "Example:\n"
        "```json\n"
        "{\"task\": \"Add a new API endpoint\", \"files\": [\"src/api/routes/new.py\", \"src/services/new_service.py\"], \"steps\": [\"Create route file\", \"Add service logic\", \"Register in app.py\", \"Add tests\"]}\n"
        "```"
    ),
    "pitfalls": (
        "You MUST return an array of objects, each with ALL of:\n"
        "- \"area\": str — the area of the codebase (e.g. \"Database\", \"Authentication\", \"Caching\")\n"
        "- \"description\": str — the non-obvious gotcha or common mistake\n"
        "- \"recommendation\": str — how to avoid or handle it\n"
        "\n"
        "Example:\n"
        "```json\n"
        "{\"area\": \"Database\", \"description\": \"SQLite has no concurrent write support\", \"recommendation\": \"Use WAL mode or queue writes\"}\n"
        "```"
    ),
    "development_rules": (
        "You MUST return an array of objects, each with ALL of:\n"
        "- \"category\": one of \"dependency_management\", \"testing\", \"code_style\", \"ci_cd\", \"environment\", \"git\"\n"
        "- \"rule\": str — the imperative rule (e.g. \"Always use TypeScript strict mode\")\n"
        "- \"source\": str — where this rule comes from (e.g. \"tsconfig.json strict: true\")\n"
        "\n"
        "Example:\n"
        "```json\n"
        "{\"category\": \"code_style\", \"rule\": \"Always use TypeScript strict mode\", \"source\": \"tsconfig.json strict: true\"}\n"
        "```"
    ),
    "quick_reference": (
        "You MUST return a JSON object with these exact keys:\n"
        "- \"where_to_put_code\": dict mapping task descriptions to directory paths\n"
        "    e.g. {\"new API endpoint\": \"src/api/routes/\", \"new service\": \"src/services/\"}\n"
        "- \"pattern_selection\": array of objects, each with ALL of:\n"
        "    - \"scenario\": str — when this applies (e.g. \"long-running task\")\n"
        "    - \"pattern\": str — recommended pattern (e.g. \"Background job via worker queue\")\n"
        "    - \"scope\": array of component names from components.components[].name where this entry\n"
        "        legitimately applies. Empty array means \"applies repo-wide\". Same semantics as the\n"
        "        scope field on implementation_guidelines and communication.patterns: the renderer\n"
        "        translates non-empty scope into rule-file globs, so out-of-scope edits never load\n"
        "        the entry. Use this to keep domain-specific recommendations out of the menu shown to\n"
        "        agents editing unrelated components — for example a concurrency primitive whose\n"
        "        invariant only holds within certain domains.\n"
        "    Example: [{\"scenario\": \"long-running task\", \"pattern\": \"Background job via worker queue\", \"scope\": []}, {\"scenario\": \"concurrent mutation of one entity row\", \"pattern\": \"Per-key advisory lock\", \"scope\": [\"<domain-A>\", \"<domain-B>\"]}]\n"
        "- \"error_mapping\": array of {\"error\": str, \"status_code\": int, \"description\": str}\n"
        "    e.g. {\"error\": \"NotFoundError\", \"status_code\": 404, \"description\": \"Resource does not exist\"}"
    ),
}


# ---------------------------------------------------------------------------
# Coordinator prompt
# ---------------------------------------------------------------------------


def build_coordinator_prompt(
    scan: RawScan,
    groups: list[SubagentAssignment],
) -> str:
    """Build the system prompt for the Opus coordinator.

    The coordinator never reads source code directly.  It receives reports
    from subagents and merges them into a single StructuredBlueprint JSON.
    """
    frameworks = ", ".join(f.name for f in scan.framework_signals) or "none detected"
    total_files = len(scan.file_tree)
    total_tokens = sum(scan.token_counts.values())
    entry_points = ", ".join(scan.entry_points[:20]) or "none detected"

    # Dependencies (cap at 50)
    dep_lines = [f"  - {d.name} {d.version}".strip() for d in scan.dependencies[:50]]
    deps_block = "\n".join(dep_lines) if dep_lines else "  (none)"

    # File tree (cap at 200)
    tree_lines = [f"  {e.path}" for e in scan.file_tree[:200]]
    tree_block = "\n".join(tree_lines) if tree_lines else "  (empty)"

    # Subagent group summary
    group_lines: list[str] = []
    for i, g in enumerate(groups, 1):
        group_lines.append(
            f"  Group {i}: {len(g.files)} files, "
            f"{g.token_total} tokens, module: {g.module_hint or 'mixed'}"
        )
    groups_block = "\n".join(group_lines) if group_lines else "  (no groups)"

    return f"""\
You are the architecture coordinator for a repository analysis.

## Repository summary
- Detected frameworks: {frameworks}
- Total files: {total_files}
- Total tokens: {total_tokens}
- Entry points: {entry_points}

## Dependencies
{deps_block}

## File tree
{tree_block}

## Subagent groups
{groups_block}

## Instructions
You do NOT read source code yourself.  You will receive reports from
subagent analysts — one per group listed above.  Your responsibilities:

1. Merge all subagent reports into a single StructuredBlueprint JSON object.
2. Resolve contradictions between reports (prefer the report with more
   evidence or higher-confidence signals).
3. Fill cross-cutting sections that no single subagent can determine alone
   (e.g. communication patterns across module boundaries, overall
   architecture_rules, deployment topology).
4. Ensure every section of the blueprint is populated; mark sections as
   "not detected" only when no subagent provided relevant data.
5. Output valid JSON conforming to the StructuredBlueprint schema.

## Completeness Validation
Before producing your final output, validate that EACH section meets these
minimum requirements:

- **meta**: Has executive_summary (3-5 sentences), platforms list, and
  confidence scores for every section (architecture_rules, decisions,
  components, communication, technology, frontend, deployment).
- **architecture_rules**: Has at least one file_placement_rule with all 5
  fields (component_type, naming_pattern, location, example, description)
  AND at least one naming_convention with all 4 fields (scope, pattern,
  examples, description).
- **decisions**: Has architectural_style with title/chosen/rationale/
  alternatives_rejected, at least one key_decision, and trade_offs.
- **components**: Has structure_type set, at least one component with ALL
  fields (name, location, responsibility, platform, depends_on, exposes_to,
  key_interfaces, key_files), and contracts if applicable.
- **communication**: Has at least one pattern with all 4 fields (name,
  when_to_use, how_it_works, examples), and integrations if any exist.
- **technology**: Has stack entries with category/name/version/purpose,
  project_structure as ASCII tree, and run_commands.
- **frontend**: If frontend code exists — ALL fields must be populated
  (framework, rendering_strategy, ui_components, state_management, routing,
  data_fetching, styling, key_conventions). If no frontend, use empty defaults.
- **deployment**: Has runtime_environment, ci_cd, and key_files at minimum.
- **developer_recipes**: At least one recipe with task, files, and steps.
- **pitfalls**: At least one pitfall with area, description, recommendation.

If any section is missing required fields, synthesize them from available
subagent reports and repository context before outputting.

## Target Schema
The output must conform to this complete StructuredBlueprint schema:

```json
{_BLUEPRINT_SCHEMA_EXAMPLE}
```
"""


# ---------------------------------------------------------------------------
# Import graph helpers
# ---------------------------------------------------------------------------


def _top_level_module(path: str) -> str:
    """Return the first path component as the module name."""
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


def _module_dependencies(
    assignment: SubagentAssignment,
    scan: RawScan,
) -> tuple[set[str], set[str], list[str]]:
    """Compute cross-module dependency info for a subagent assignment.

    Returns:
        imports_from: set of module names this assignment's files import from
        imported_by: set of module names that import from this assignment's files
        entry_points: files in this assignment that appear in scan.entry_points
    """
    assigned_set = set(assignment.files)
    # Determine which modules the assigned files belong to.
    own_modules: set[str] = set()
    for f in assignment.files:
        mod = _top_level_module(f)
        if mod:
            own_modules.add(mod)

    imports_from: set[str] = set()
    imported_by: set[str] = set()

    for source_file, targets in scan.import_graph.items():
        source_mod = _top_level_module(source_file)

        if source_file in assigned_set:
            # This file belongs to our assignment — its targets are our deps.
            for target in targets:
                target_mod = _top_level_module(target)
                if target_mod and target_mod not in own_modules:
                    imports_from.add(target_mod)
        else:
            # External file — check if it imports from our assignment's files.
            for target in targets:
                if target in assigned_set:
                    if source_mod and source_mod not in own_modules:
                        imported_by.add(source_mod)

    entry_points = [f for f in assignment.files if f in scan.entry_points]

    return imports_from, imported_by, entry_points


# ---------------------------------------------------------------------------
# Subagent prompt
# ---------------------------------------------------------------------------


def build_subagent_prompt(
    assignment: SubagentAssignment,
    scan: RawScan,
) -> str:
    """Build the system prompt for a Sonnet subagent.

    Each subagent reads the files in its assignment and fills the requested
    blueprint sections with structured JSON.
    """
    frameworks = ", ".join(f.name for f in scan.framework_signals) or "none detected"

    dep_names = ", ".join(d.name for d in scan.dependencies[:50]) or "none"

    file_list = "\n".join(f"  - {f}" for f in assignment.files) or "  (none)"

    section_list = "\n".join(f"  - {s}" for s in assignment.sections) or "  (none)"

    # Build schema guidance for the assigned sections
    guidance_lines: list[str] = []
    for section in assignment.sections:
        hint = _SECTION_GUIDANCE.get(section, "Populate according to schema.")
        guidance_lines.append(f"### {section}\n{hint}")
    guidance_block = "\n\n".join(guidance_lines)

    # Module dependency context from import graph
    imports_from, imported_by, entry_points = _module_dependencies(assignment, scan)
    dep_section_lines: list[str] = []
    if imports_from:
        dep_section_lines.append(
            "- Imports from modules: " + ", ".join(sorted(imports_from))
        )
    if imported_by:
        dep_section_lines.append(
            "- Imported by modules: " + ", ".join(sorted(imported_by))
        )
    if entry_points:
        dep_section_lines.append(
            "- Entry points: " + ", ".join(entry_points)
        )
    module_deps_block = ""
    if dep_section_lines:
        module_deps_block = (
            "\n## Module Dependencies\n" + "\n".join(dep_section_lines) + "\n"
        )

    return f"""\
You are a code analyst subagent responsible for module: {assignment.module_hint or 'general'}.

## Context
- Detected frameworks: {frameworks}
- Known dependencies: {dep_names}
- Assigned module: {assignment.module_hint or 'general'}
{module_deps_block}
## Files to read
{file_list}

## Blueprint sections to fill
{section_list}

## Schema guidance per section

{guidance_block}

## Complete StructuredBlueprint schema reference

Below is the FULL schema with example values for every field. Your output
sections must conform to this structure exactly. Every field shown is
required — do not omit fields even if the value is an empty string or array.

```json
{_BLUEPRINT_SCHEMA_EXAMPLE}
```

## Critical field requirements

For each **component** you MUST provide: name, location, responsibility,
platform, depends_on, exposes_to, key_interfaces, key_files.

For each **decision** you MUST provide: title, chosen, rationale,
alternatives_rejected.

For **meta** you MUST include: executive_summary (3-5 factual sentences),
platforms list, confidence scores per section (architecture_rules, decisions,
components, communication, technology, frontend, deployment — each 0.0-1.0).

For **technology.templates** you MUST include actual code samples from the
codebase showing the boilerplate pattern used for each component type.

For **technology.project_structure** you MUST provide an ASCII directory tree
showing the actual project layout.

If **frontend** code exists, fill ALL fields: framework, rendering_strategy,
ui_components (each with name, location, component_type, description, props,
children), state_management (with approach, global_state, server_state, local_state, rationale),
routing (each with path, component, description, auth_required),
data_fetching (each with name, mechanism, when_to_use, examples),
styling, key_conventions. If no frontend exists, omit or use empty defaults.

## Output format
Return a valid JSON dict keyed by section name.  Each key must be one of the
section names listed above.  Example:

```json
{{
  "components": {{...}},
  "technology": {{...}}
}}
```

## Focus
Concentrate on architectural insights that an AI cannot infer from
individual files in isolation: cross-file relationships, implicit contracts,
non-obvious design decisions, and integration patterns.
"""
