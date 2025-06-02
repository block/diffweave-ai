# DiffWeave AI

DiffWeave is a tool that automatically generates meaningful Git commit messages using large language models (LLMs). It analyzes your staged changes and creates descriptive commit messages, saving you time and ensuring consistent documentation.

[Documentation available here](https://special-guide-7j359k7.pages.github.io/)

![Demo](docs/images/demo.png)

## Installation & Quick Start

DiffWeave is installed as an isolated tool using `uv`:

```bash
# Make sure you have uv installed first
# https://docs.astral.sh/uv/getting-started/installation/

uvx diffweave-ai
```

```bash
# Basic usage
uvx diffweave commit

# With specific model
uvx diffweave commit --model "your-model-name"
```

## Features

- AI-powered commit message generation
- Interactive file selection for unstaged changes
- Support for various LLM providers
- Custom context to guide message generation
- Interactive workflow with message review