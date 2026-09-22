#!/usr/bin/env python3
"""Verify that all dependencies are installed and the environment is ready."""

import sys

def check_imports():
    """Check that all required packages are importable."""
    required = [
        "fastapi", "uvicorn", "pydantic", "openai", "tiktoken",
        "sentence_transformers", "faiss", "numpy", "pandas",
        "sqlalchemy", "httpx", "dotenv", "tqdm", "rich",
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"FAIL: Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    print("OK: All packages importable.")
    return True


def check_env():
    """Check that .env file exists."""
    from pathlib import Path
    if not Path(".env").exists():
        print("WARN: .env file not found. Copy .env.example to .env and add your API key.")
        return False
    print("OK: .env file found.")
    return True


def check_api_key():
    """Check that OpenRouter API key is set."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key == "your-openrouter-api-key-here":
        print("WARN: OPENROUTER_API_KEY not set in .env")
        return False
    print("OK: API key configured.")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("NDATrace Environment Verification")
    print("=" * 50)
    print()

    results = [
        check_imports(),
        check_env(),
        check_api_key(),
    ]

    print()
    if all(results):
        print("All checks passed! Ready to go.")
    else:
        print("Some checks failed. See warnings above.")
        sys.exit(1)
