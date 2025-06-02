"""
DiffWeave - LLM-powered Git Commit Message Generator

This module provides tools for generating git commit messages using LLMs.
It includes functionality for interacting with git repositories, configuring
custom LLM models, and generating commit messages based on staged changes.

Main components:
- utils: Command execution utilities
- models: LLM model configuration
- interface: User interface for git operations
- cli: Command-line interface for the tool
"""

from .utils import run_cmd
from . import ai
from . import repo
from .cli import app
