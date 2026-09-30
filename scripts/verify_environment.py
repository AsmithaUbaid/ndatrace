#!/usr/bin/env python3
"""Verify local dependencies and optionally require hosted-model credentials."""

import argparse
import sys

def check_imports():
    """Check that all required packages are importable."""
    required = [
        "fastapi", "uvicorn", "pydantic", "openai", "tiktoken",
        "sentence_transformers", "faiss", "numpy", "pandas",
        "httpx", "dotenv", "tqdm", "rich",
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
    """Check whether an optional local .env file exists."""
    from pathlib import Path
    if not Path(".env").exists():
        print("WARN: .env file not found; safe defaults will be used.")
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-api-key",
        action="store_true",
        help="fail unless a non-placeholder OPENROUTER_API_KEY is configured",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("NDATrace Environment Verification")
    print("=" * 50)
    print()

    imports_ok = check_imports()
    check_env()
    api_key_ok = check_api_key()

    print()
    if imports_ok and (api_key_ok or not args.require_api_key):
        if api_key_ok:
            print("All checks passed! Hosted review calls are enabled.")
        else:
            print("Offline/startup checks passed. Hosted review calls remain disabled.")
    else:
        print("Required checks failed. See messages above.")
        sys.exit(1)
