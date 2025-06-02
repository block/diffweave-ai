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

#### Configuring the completion endpoint

```bash
uvx diffweave add-custom-model \
    --model "name-of-your-model" \
    --endpoint "https://endpoint-url" \
    --token $TOKEN
```

This will prompt you for the API token for the model. Do NOT clutter your shell history with
this token!

##### Example: Databricks Endpoint Configuration

Get a token from Databricks and set it as the environment variable `DATABRICKS_TOKEN`:

```bash
uvx diffweave add-custom-model \
    --model "claude-3-7-sonnet" \
    --endpoint "https://block-lakehouse-production.cloud.databricks.com/serving-endpoints" \
    --token $DATABRICKS_TOKEN
```

#### Configuring the default model to use

Finally, in order to ensure that `diffweave` uses the model you just configured, you need to set it as the default model:

```bash
uvx diffweave set-default-llm-model claude-3-7-sonnet
```

#### Using diffweave

Basic usage - examine the current repo, stage files for commit, and generate a commit message:

```bash
uvx diffweave commit
```

If you want to specify the model to run you can add the `--model` flag:

```bash
uvx diffweave commit --model "claude-3-7-sonnet"
```
