# DiffWeave

DiffWeave is a tool for automatically generating commit messages using large language models (LLMs). 
The goal is for this tool to be intuitive to use and to help you write meaningful commit messages.

![png](images/demo.gif)

## Getting Started

### Dependencies

Ensure you have the following dependencies installed:

* [git](https://git-scm.com/downloads/linux)
* [tree](https://linux.die.net/man/1/tree)
* [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

Once `uv` is all set up on your shell, you can install `diffweave` with the following command:

```bash
uvx diffweave-ai
```

This will install `diffweave` as a "tool", in an isolated virtual environment with its own version
of python and all required dependencies!
[Check out the docs here for more information on tools](https://docs.astral.sh/uv/guides/tools/)

### Usage

#### Configuring a model endpoint

```bash
uvx diffweave-ai add-model \
    --model "name-of-your-model" \
    --endpoint "https://endpoint-url" \
    --token "$TOKEN"
```

This stores the model configuration in your local diffweave config file so it can be reused across runs. Do NOT clutter your shell history with the raw token—set it as an environment variable and reference it as shown above.

##### Example: Databricks Endpoint Configuration

Get a token from Databricks and set it as the environment variable `DATABRICKS_TOKEN`:

```bash
uvx diffweave-ai add-model \
    --model "claude-3-7-sonnet" \
    --endpoint "https://block-lakehouse-production.cloud.databricks.com/serving-endpoints" \
    --token "$DATABRICKS_TOKEN"
```

#### Configuring the default model to use

Finally, in order to ensure that `diffweave` uses the model you just configured, you need to set it as the default model:

```bash
uvx diffweave-ai set-default "claude-3-7-sonnet"
```

#### Using diffweave

Basic usage - examine the current repo, stage files for commit, and generate a commit message:

```bash
uvx diffweave-ai
```

If you want to specify the model to run you can add the `--model` / `-m` flag:

```bash
uvx diffweave-ai -m "claude-3-7-sonnet"
```

If you prefer a simpler, more natural-language commit style rather than Conventional Commits, pass `--simple`:

```bash
uvx diffweave-ai --simple
```

You can also run in dry-run mode (generate and print a commit message without committing):

```bash
uvx diffweave-ai --dry-run
```

Or in a non-interactive mode, which will generate a message and attempt to commit and push without additional prompts:

```bash
uvx diffweave-ai --non-interactive
```

During a normal interactive `uvx diffweave-ai` run the CLI will:

- Show `git status` for your current repository.
- Offer to stage changes using git.
- Generate a commit message using your configured model and internal prompt.
- Let you review/refine the message.
- Attempt `git commit -m "<message>"`.
- Optionally run `git push` and, if the push output includes a URL, offer to open it in your browser to create a PR.
