# Architecture MCP Server

A Model Context Protocol (MCP) server that exposes architecture blueprints as persistent context for AI-assisted development. This server ensures your architectural patterns, principles, and conventions are always available to AI tools like Cursor, maintaining architectural integrity throughout the development lifecycle.

---

## 🎯 Key Benefits

### 1. **Persistent Context - Always Available**

**Problem:** Traditional development requires repeatedly pasting architecture documentation into AI conversations. Each new chat starts from scratch, losing architectural context.

**Solution:** Blueprints become **always available** to the AI without you having to paste them repeatedly. Once configured, your architecture documentation is permanently accessible to Cursor and other MCP-compatible tools.

- ✅ No more copying/pasting architecture docs
- ✅ Architecture knowledge persists across conversations
- ✅ Context is maintained automatically
- ✅ Works across all projects and repositories

**Impact:** Every AI interaction has access to your architectural guidelines, ensuring consistent, informed suggestions from the start.

---

### 2. **Single Source of Truth**

**Problem:** Architecture documentation scattered across multiple files, wikis, or outdated documents. Updates require manual synchronization across platforms.

**Solution:** **One place to update architecture docs, automatically reflected in AI assistance.** The `DOCS/` directory is your single source of truth - update it once, and all AI interactions immediately reflect the changes.

- ✅ Centralized architecture documentation
- ✅ Update once, benefit everywhere
- ✅ Version-controlled with your codebase
- ✅ No synchronization issues
- ✅ Consistent information across all AI interactions

**Impact:** Architectural decisions and updates are immediately available to all developers and AI tools, eliminating inconsistencies and outdated information.

---

### 3. **Proactive Guardrails**

**Problem:** AI suggests code that violates architectural patterns because it lacks access to your specific guidelines. You only discover violations during code review or runtime.

**Solution:** **The AI can reference blueprints before suggesting code that might violate patterns.** The MCP server provides validation tools and pattern references that guide AI suggestions proactively.

- ✅ Pattern-aware code generation
- ✅ Pre-emptive validation
- ✅ Architectural guidance before implementation
- ✅ Reduced architectural debt
- ✅ Consistent pattern usage

**Impact:** AI-generated code aligns with your architecture from the start, reducing refactoring and maintaining architectural integrity throughout development.

---

## 📋 What This Project Provides

### Architecture Blueprints

Structured documentation covering:

- **Backend Architecture**
  - Layer architecture (Presentation, Application, Domain, Infrastructure)
  - SOLID principles and core patterns
  - Communication patterns (Sync, Streaming, Service Registry, etc.)
  - Component contracts and interfaces
  - Error handling strategies
  - Implementation guides

- **Frontend Architecture**
  - Project structure conventions
  - React patterns (Context + Hooks, Query Hooks, etc.)
  - Service abstraction patterns
  - Component organization
  - Implementation guides

- **Shared Documentation**
  - Common anti-patterns
  - Architectural decision records
  - Best practices

### MCP Tools

The server exposes tools for:

- **Query Tools**
  - `get_pattern` - Get detailed pattern information
  - `list_patterns` - List all available patterns
  - `get_layer_rules` - Get layer constraints and rules
  - `get_principle` - Get architectural principles (SRP, DIP, etc.)

- **Validation Tools**
  - `check_layer_violation` - Detect layer boundary violations
  - `check_file_placement` - Validate file structure
  - `suggest_pattern` - Recommend patterns for use cases
  - `review_component` - Review code for compliance

### MCP Resources

Full access to architecture documentation:

- Complete blueprint documents
- Individual sections and patterns
- Pattern indexes
- Implementation guides

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Virtual environment support (venv)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd architecture_mcp
   ```

2. **Run the startup script** (handles everything automatically)
   ```bash
   python3 start.py
   # Or: ./start.sh (Unix/Mac)
   # Or: start.bat (Windows)
   ```

   The script will:
   - ✅ Check Python version
   - ✅ Create/activate virtual environment
   - ✅ Install dependencies
   - ✅ Verify documentation structure
   - ✅ Display Cursor integration guide

### Cursor Integration

The startup script displays the exact configuration needed. Add this to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "architecture": {
      "command": "/absolute/path/to/architecture_mcp/.venv/bin/python",
      "args": ["/absolute/path/to/architecture_mcp/run_server.py"],
      "cwd": "/absolute/path/to/architecture_mcp"
    }
  }
}
```

**Location:** Cursor Settings → Features → Model Context Protocol → Edit Config

---

## 📖 Usage Examples

### Getting Architectural Guidance

```
You: "I need to implement user authentication. What pattern should I use?"

Cursor: [Consults MCP server]
→ Uses get_pattern or suggest_pattern tool
→ Returns: "Based on your architecture, use the Service Registry pattern 
   for authentication providers. Here's the pattern..."
```

### Validating Code

```
You: "Check if this service class violates our layer rules"

Cursor: [Uses check_layer_violation tool]
→ Validates against backend layer rules
→ Returns: "⚠️ Warning: Service imports FastAPI directly. 
   Application layer should not know about HTTP. Move to Presentation layer."
```

### Pattern Reference

```
You: "How should I structure my React hooks for server state?"

Cursor: [Uses get_pattern with "query-hooks"]
→ Returns pattern details from frontend blueprint
→ Shows example code matching your architecture
```

### File Structure Validation

```
You: "Is this file in the right location? src/hooks/auth.ts"

Cursor: [Uses check_file_placement tool]
→ Validates against frontend structure rules
→ Returns: "✅ Correct location. hooks/ directory is for custom hooks."
```

---

## 🏗️ Project Structure

```
architecture_mcp/
├── DOCS/                          # Architecture blueprints (Single Source of Truth)
│   ├── backend/                   # Backend architecture documentation
│   │   ├── _index.md
│   │   ├── principles.md
│   │   ├── layers.md
│   │   ├── patterns/
│   │   ├── contracts.md
│   │   ├── errors.md
│   │   └── implementation.md
│   ├── frontend/                  # Frontend architecture documentation
│   │   ├── _index.md
│   │   ├── principles.md
│   │   ├── structure.md
│   │   ├── patterns/
│   │   ├── services.md
│   │   └── implementation.md
│   └── shared/                    # Shared documentation
│       └── anti-patterns.md
│
├── src/                           # MCP server implementation
│   ├── server.py                  # Main server entry point
│   ├── resources.py               # Resource handlers
│   ├── tools.py                   # Tool implementations
│   ├── validators.py              # Validation logic
│   └── utils/                     # Utility functions
│
├── run_server.py                  # Server entry point script
├── start.py                       # Cross-platform startup script
├── start.sh                       # Unix/Mac startup script
├── start.bat                      # Windows startup script
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

---

## 🔧 How It Works

### MCP Protocol

This server implements the [Model Context Protocol](https://modelcontextprotocol.io/), allowing AI tools to:

1. **Access Resources** - Read architecture documentation
2. **Call Tools** - Query patterns, validate code, get guidance
3. **Maintain Context** - Keep architectural knowledge available

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cursor / AI Tool                         │
└───────────────────────┬─────────────────────────────────────┘
                        │ MCP Protocol
                        │ (stdio communication)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Architecture MCP Server                        │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Resources   │  │    Tools     │  │  Validators  │    │
│  │  Handler     │  │  Handler     │  │   Logic      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │            │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   DOCS/ Directory                           │
│            (Single Source of Truth)                         │
│                                                             │
│  • Backend blueprints                                       │
│  • Frontend blueprints                                      │
│  • Patterns & principles                                    │
│  • Implementation guides                                    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User asks Cursor** about architecture or code
2. **Cursor detects** relevance to architecture
3. **Cursor calls MCP tools** (get_pattern, validate, etc.)
4. **MCP server** reads from DOCS/ directory
5. **Server returns** structured information
6. **Cursor uses information** to provide informed response

---

## 📝 Maintaining Your Blueprints

### Updating Documentation

The `DOCS/` directory is your **single source of truth**. To update:

1. Edit the relevant markdown files in `DOCS/`
2. Changes are immediately available (no restart needed)
3. All AI interactions reflect updates automatically

### Document Structure

Each document includes frontmatter metadata:

```yaml
---
id: backend-layer-architecture
title: Layer Architecture
category: backend
tags: [layers, domain, infrastructure]
related: [backend-principles]
---
```

This enables:
- Pattern ID-based lookups
- Tag-based filtering
- Related document navigation
- Structured queries

### Adding New Patterns

1. Create a new markdown file in `DOCS/backend/patterns/` or `DOCS/frontend/patterns/`
2. Add frontmatter with unique ID
3. Document the pattern following existing structure
4. Update pattern index (`_index.md`) if needed

---

## 🎓 Best Practices

### For Maximum Benefit

1. **Start conversations with context**
   ```
   "I'm building a new feature. Please reference our architecture 
   patterns and validate all suggestions."
   ```

2. **Be explicit about validation**
   ```
   "Check this code against our backend layer rules"
   "Validate this component for architectural compliance"
   ```

3. **Reference patterns explicitly**
   ```
   "Use our Service Registry pattern for this"
   "Follow our Context + Hook pattern here"
   ```

4. **Regular validation**
   - Validate code before committing
   - Check patterns when unsure
   - Review architectural decisions

### Workflow Integration

- **Before coding:** Ask for pattern recommendations
- **During coding:** Reference patterns when stuck
- **After coding:** Validate for compliance
- **Before committing:** Run validation checks

---

## 🔮 Future Enhancements

Potential improvements for stronger guardrail behavior:

- **Pre-commit hooks** - Automatic validation before commits
- **CI/CD integration** - Build-time architecture checks
- **Static analysis rules** - Custom linters for patterns
- **Architecture tests** - Automated pattern verification
- **Dependency analysis** - Layer boundary enforcement
- **Real-time validation** - IDE integration for live checks

---

## 🤝 Contributing

This is a template/starting point for your team's architecture documentation. Customize it to match your:

- Specific patterns and conventions
- Technology stack
- Team preferences
- Project requirements

---

## 📚 Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Cursor MCP Integration Guide](https://docs.cursor.com/advanced/mcp)
- Architecture blueprints in `DOCS/` directory

---

## 📄 License

MIT License - Customize and use as needed for your projects.

---

## ⚡ Quick Reference

**Start the server:**
```bash
python3 start.py
```

**Get Cursor config:**
Run `start.py` and copy the configuration from the integration guide

**Update blueprints:**
Edit files in `DOCS/` directory

**Test server:**
```bash
.venv/bin/python run_server.py
```

---

**Remember:** Your architecture blueprints are now **always available**, maintained as a **single source of truth**, and provide **proactive guardrails** for AI-assisted development. Update once, benefit everywhere! 🚀
