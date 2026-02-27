# Getting Started

## Dependencies

Ensure you have the following dependencies installed:

* [git](https://git-scm.com/downloads/linux)
* [tree](https://linux.die.net/man/1/tree) *(optional — used for pretty file-tree display when staging)*
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

Once `uv` is set up on your shell, install `diffweave-ai` with:

```bash
uvx diffweave-ai
```

This installs `diffweave-ai` as a uv tool in an isolated virtual environment with its own Python and all required dependencies.
[See the uv tools documentation for more information.](https://docs.astral.sh/uv/guides/tools/)

# Configuration

DiffWeave stores a single active model configuration at `~/.config/diffweave/config.yaml`. Running either setup command below will create or overwrite this file.

## Token-authenticated models (OpenAI-compatible)

Use `set-token-model` for any OpenAI-compatible endpoint — including OpenAI itself, Azure OpenAI, Anthropic, or a self-hosted model:

```bash
uvx diffweave-ai set-token-model "your-model-name" \
    --token "$YOUR_API_TOKEN" \
    --endpoint "https://your-endpoint-url"
```

The `--endpoint` flag defaults to `https://api.openai.com/v1/responses` if omitted.

Do **not** paste raw tokens directly into your shell history. Set the token as an environment variable and reference it as shown above.

### Example: OpenAI

```bash
uvx diffweave-ai set-token-model "gpt-4o" \
    --token "$OPENAI_API_KEY"
```

### Example: Custom / self-hosted endpoint

```bash
uvx diffweave-ai set-token-model "claude-3-5-sonnet-20241022" \
    --token "$MY_API_TOKEN" \
    --endpoint "https://my-llm-gateway.example.com/v1"
```

## Databricks-hosted models (browser authentication)

Use `set-databricks-browser-model` to configure a model hosted on Databricks. Authentication is handled via browser login — no token management required:

```bash
uvx diffweave-ai set-databricks-browser-model "databricks-meta-llama-3-3-70b-instruct" \
    --account "my-org"
```

On first use (and whenever the cached token expires), a browser window will open for you to authenticate. The resulting token is cached locally and reused for subsequent runs.

## Verifying your configuration

After configuring a model, run a quick dry-run to confirm everything is working:

```bash
uvx diffweave-ai --dry-run
```

The model name in use is shown at the top of every run.
