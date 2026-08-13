"""gbt7714-lint: linter and auto-fixer for GB/T 7714-2025 bibliographies."""

from .config import Config
from .linter import fix_text, lint_text
from .models import Entry, Issue

__version__ = "0.3.0"

__all__ = ["lint_text", "fix_text", "Config", "Entry", "Issue", "__version__"]
