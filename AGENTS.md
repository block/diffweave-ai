# AGENTS.md — DiffWeave AI

This file is a quick-start guide for AI coding assistants (Claude Code, etc.) working on this project.

---

## Project Overview

**DiffWeave AI** is a CLI tool that automatically generates Git commit messages and pull request descriptions using LLMs. It analyzes staged diffs and produces descriptive messages in either Conventional Commits or natural language style.

- **Package name:** `diffweave-ai` (PyPI) / `diffweave` (Python package)
- **Version:** 1.2.2
- **Entry point:** `diffweave:app` → `diffweave/cli.py`
- **Current branch:** `zfarmer/dev` (main branch is `main`)

---

## Tech Stack

| Concern | Tool |
|---|---|
| Language | Python 3.9+ (target 3.12) |
| CLI framework | [cyclopts](https://github.com/BrainStone/cyclopts) (migrated from typer) |
| LLM client | `openai` SDK (supports custom HTTP endpoints) |
| Git operations | `gitpython` |
| Interactive TUI | `beaupy` (multi-select, prompts) |
| Clipboard | `copykitten` |
| Config format | YAML via `pyyaml` |
| Package manager | `uv` (lock file: `uv.lock`) |
| Build system | `hatchling` |
| Linter/formatter | `ruff` (line-length=120, double quotes) |
| Tests | `pytest` + `pytest-asyncio`, `pytest-cov`, `pytest-mock` |
| Docs | `mkdocs` + `mkdocs-material` |
| Task runner | `just` (see `justfile`) |

---

## Key Development Commands

```bash
just format        # ruff format (alias: just fmt)
just test          # pytest with coverage (all tests)
just test tests/test_cli.py  # run specific test file
just commit        # run diffweave-ai locally (uv run diffweave-ai)
just docs          # build mkdocs and open site/index.html

uv run diffweave-ai          # run the tool from local checkout
uvx diffweave-ai             # run as isolated tool (published version)
```

---

## Project Structure

```
diffweave/
├── __init__.py          # Package exports: run_cmd, ai, repo, app
├── cli.py               # All CLI command definitions (206 lines)
├── ai.py                # LLM config, model management, message generation (204 lines)
├── repo.py              # Git operations and diff generation (218 lines)
├── utils.py             # run_cmd() shell helper with rich formatting (70 lines)
└── prompts/
    ├── prompt.md        # Conventional Commits style system prompt
    ├── simple.md        # Natural language style system prompt
    └── pull_request.md  # PR description generation prompt

tests/
├── conftest.py          # Fixtures: patch_openai, new_repo, config_file, populated_config
├── test_cli.py          # CLI command integration tests
├── test_repo.py         # Repository operations tests
├── test_ai.py           # LLM interaction tests
├── test_run_cmd.py      # Shell command execution tests
├── test_config.py       # (placeholder, empty)
└── test_unix_commands.py

docs/
├── index.md             # CLI reference guide
└── installation.md      # Setup and configuration guide

pyproject.toml           # Dependencies and ruff/mypy config
justfile                 # Task automation
mkdocs.yml               # Docs build config
```

---

## CLI Commands

```bash
# Default: generate a commit message (interactive)
diffweave-ai [-m MODEL] [-s] [--dry-run] [--non-interactive] [-v] [-w] [-c CONFIG]

# Model management
diffweave-ai add-model [-m MODEL] [-t TOKEN] [-e ENDPOINT] [-c CONFIG]
diffweave-ai set-model MODEL_NAME [-c CONFIG]
diffweave-ai list-models [-c CONFIG]

# PR description generation
diffweave-ai pr [--branch BRANCH] [-m MODEL] [-v] [-c CONFIG]
```

**Flags for default command:**
- `-s / --simple` — natural language style (omits Conventional Commits prefix)
- `--dry-run` — generate message and exit without committing
- `--non-interactive` — skip all prompts, use first generated message
- `-w / --open-browser` — open repo in browser after push

---

## Configuration

**Default config location:** `~/.config/diffweave/config.yaml`

```yaml
<<DEFAULT>>: my-model
my-model:
  endpoint: https://api.openai.com/v1
  token: sk-...
another-model:
  endpoint: https://custom-endpoint.com/v1
  token: token-here
```

- Tokens are redacted when listed
- Legacy config auto-migrates from `~/.config/llmit/config.yaml`
- `--config / -c` flag overrides default path

---

## Architecture Notes

### `diffweave/cli.py`
- `commit()` (line 21) — main flow: init LLM → get repo → stage files → generate diffs → iterate with user → git commit/push
- `pr()` (line 128) — branch diff → LLM → output PR description
- Model config commands: `add_model`, `set_model`, `list_models`

### `diffweave/ai.py`
- `LLM` class wraps OpenAI client with custom endpoint support
- `iterate_on_commit_message()` — feedback loop: generate → review → refine
- `query_model()` — async method that calls LLM with system prompt + user content
- Config stored/loaded from YAML; prompts loaded from `diffweave/prompts/*.md`

### `diffweave/repo.py`
- `get_repo()` — searches parent directories for `.git`
- `generate_diffs_with_context()` — main entry point; handles first commit edge case
- `add_files()` — beaupy multi-select for interactive staging
- `MAX_DIFF_ITEM_SIZE = 40_000` — truncates large files to prevent token overflow
- GitHub URL regex handles SSH, HTTPS, and `git://` remote formats

### `diffweave/utils.py`
- `run_cmd(cmd: str, ...)` — runs shell commands, formats output, raises `SystemError` on non-zero exit

---

## Testing Conventions

- All tests use `patch_openai` autouse fixture (mocks OpenAI client globally)
- `new_repo()` fixture creates a real temp git repo for integration tests
- `populated_config()` provides a ready-made YAML config fixture
- Run with: `uv run pytest --cov=diffweave --cov-branch tests/`

---

## Code Style

- **Formatter:** ruff (double quotes, 4-space indent, line-length=120)
- **Import errors ignored:** `F401` (unused imports)
- **Type hints:** present but not strictly enforced (mypy config exists)
- Prefer editing existing files over creating new ones
- Prompts live in `diffweave/prompts/` as Markdown files — edit there, not in Python

---

## External Dependencies

Requires system-level tools:
- `git` — version control
- `tree` — used for directory display in UI
