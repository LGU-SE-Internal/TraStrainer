#!/usr/bin/env python3
"""Task runner script for TraStrainer using uv."""

import subprocess
import sys


def run_command(cmd: str, description: str):
    """Run a command using uv."""
    print(f"🔧 {description}")
    print(f"   Command: {cmd}")

    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Task failed: {description}")
        sys.exit(1)
    else:
        print(f"✅ Task completed: {description}\n")


def main():
    """Main task runner."""
    if len(sys.argv) < 2:
        print("""
🛠️ TraStrainer Task Runner

Available tasks:
  setup     - Install dependencies and sync project
  test      - Run tests
  format    - Format code
  check     - Run code checks
  sample    - Run sample with test data
  validate  - Validate test data
  info      - Show algorithm info
  build     - Build package
  clean     - Clean build artifacts
  help      - Show this help

Usage: python tasks.py <task>
或者: uv run python tasks.py <task>
        """)
        return

    task = sys.argv[1].lower()

    tasks = {
        "setup": ("uv sync --dev", "Install dependencies and sync project"),
        "test": ("uv run python test_uv.py", "Run configuration tests"),
        "format": (
            "uv run ruff format src/ examples/ && uv run ruff check --fix src/ examples/",
            "Format and fix code",
        ),
        "check": (
            "uv run ruff check src/ examples/ && uv run pyright src/",
            "Run code checks",
        ),
        "sample": (
            "uv run trastrainer sample test/ts1-ts-route-plan-service-request-replace-method-qtbhzt --rate 0.05 --verbose --format json",
            "Run sampling with test data",
        ),
        "validate": (
            "uv run trastrainer validate test/ts1-ts-route-plan-service-request-replace-method-qtbhzt",
            "Validate test data",
        ),
        "info": ("uv run trastrainer info", "Show algorithm information"),
        "build": ("uv build", "Build package"),
        "clean": (
            "rm -rf dist/ build/ *.egg-info/ .ruff_cache/ .mypy_cache/",
            "Clean build artifacts",
        ),
        "example": ("uv run python examples/uv_examples.py", "Run usage examples"),
        "complete": (
            "uv run python run_complete_test.py",
            "Run complete integration test",
        ),
    }

    if task == "help":
        print("""
🛠️ TraStrainer Task Runner

Available tasks:
""")
        for name, (cmd, desc) in tasks.items():
            print(f"  {name:<10} - {desc}")
        return

    if task in tasks:
        cmd, description = tasks[task]
        run_command(cmd, description)
    else:
        print(f"❌ Unknown task: {task}")
        print("Run 'python tasks.py help' to see available tasks")
        sys.exit(1)


if __name__ == "__main__":
    main()
