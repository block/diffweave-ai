# Getting Started

## Dependencies

Ensure you have the following dependencies installed:

* [git](https://git-scm.com/downloads/linux)
* [tree](https://linux.die.net/man/1/tree)
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

Once `uv` is all set up on your shell, you can install `diffweave` with the following command:

```bash
uvx diffweave-ai
```

This will install `diffweave` as a "tool", in an isolated virtual environment with its own version
of python and all required dependencies!
[Check out the docs here for more information on tools](https://docs.astral.sh/uv/guides/tools/)


# Configuration 

## Configuring a model endpoint

```bash
uvx diffweave-ai add-model \
    --model "name-of-your-model" \
    --endpoint "https://endpoint-url" \
    --token "$TOKEN"
```

This stores the model configuration in your local diffweave config file so it can be reused across runs. Do NOT clutter your shell history with the raw token—set it as an environment variable and reference it as shown above.

### Example: Databricks Endpoint Configuration

Get a token from Databricks and set it as the environment variable `DATABRICKS_TOKEN`:

```bash
uvx diffweave-ai add-model \
    --model "claude-3-7-sonnet" \
    --endpoint "https://block-lakehouse-production.cloud.databricks.com/serving-endpoints" \
    --token "$DATABRICKS_TOKEN"
```

## Setting the default model

To make a particular model the default for `diffweave-ai`, run:

```bash
uvx diffweave-ai set-model "claude-3-7-sonnet"
```

You can still override the model per invocation with the `--model` / `-m` flag.

## Configuration file

All model definitions and defaults are stored in a configuration file. By default, DiffWeave chooses a sensible location in your home directory, but you can override this with the `--config` / `-c` flag on any command that accepts it (for example: `add-model`, `set-model`, `list-models`, `pr`, or the default commit command).

This is useful if you:

- Maintain separate model configs for different projects or environments.
- Want to keep a project-local configuration file checked into a repository.

## Listing configured models

To see what models are currently configured in your chosen config file, run:

```bash
uvx diffweave-ai list-models
```

You can pass `--config` if you want to point at a non-default config file.
