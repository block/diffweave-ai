# DiffWeave AI

DiffWeave is a tool that automatically generates meaningful Git commit messages using large language models (LLMs). It analyzes your staged changes and creates descriptive commit messages, saving you time and ensuring consistent documentation.

[Documentation available here](https://block.github.io/diffweave-ai/)

![Demo](docs/images/demo.png)

## Installation & Quick Start

DiffWeave is installed as an isolated tool using `uv`:

```bash
# Make sure you have uv installed first
# https://docs.astral.sh/uv/getting-started/installation/

uvx diffweave-ai
```

## Usage

### Configure a model

Before generating commit messages, configure at least one model endpoint:

```bash
uvx diffweave-ai add-model \
  --model "name-of-your-model" \
  --endpoint "https://endpoint-url" \
  --token "$TOKEN"
```

Then set the default model to use:

```bash
uvx diffweave-ai set-default "name-of-your-model"
```

You can still override the model per invocation with the `--model` / `-m` flag.

### Generate a commit message

Once you have a model configured and some changes staged in your current Git repository you can run:

```bash
uvx diffweave-ai
```

This will:

- Show the current `git status`.
- Optionally stage files for you (interactive by default).
- Generate a commit message using your configured model.
- Let you review/refine the message.
- Attempt `git commit` (and optionally `git push` and PR open if a URL is printed).

To specify a model for a single run:

```bash
uvx diffweave-ai -m "your-model-name"
```

If you prefer a simpler, more natural-language commit style rather than Conventional Commits, pass `--simple`:

```bash
uvx diffweave-ai --simple
```

You can also run in dry-run mode (generate and print a commit message without committing):

```bash
uvx diffweave-ai --dry-run
```

Or in a non-interactive mode, which will generate a message and attempt to commit and push without asking follow-up questions:

```bash
uvx diffweave-ai --non-interactive
```

## Features

- AI-powered commit message generation based on staged diffs
- Interactive or non-interactive workflows
- Support for configuring custom LLM HTTP endpoints
- Ability to set and override the default model
- Optional simpler commit style via `--simple`
- Optional push and PR-open flow when `git push` prints a URL
