# This is the default recipe when no arguments are provided
[private]
default:
    @just --list

# Reformats all python with ruff
format:
    uv run ruff format

alias fmt := format

# Run Tests (can specify which file to run!)
test target='tests/':
    uv run pytest --cov=diffweave -cov-branch {{ target }}

commit:
    uv run diffweave commit

docs:
    uv run mkdocs build
    open site/index.html