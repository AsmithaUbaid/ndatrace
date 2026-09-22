#!/usr/bin/env python3
"""CLI for running NDATrace experiments."""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Run an NDATrace experiment")
    parser.add_argument("--config", required=True, help="Path to experiment config JSON")
    parser.add_argument("--dry-run", action="store_true", help="Show config without running")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    print(f"Experiment: {config.get('experiment_id', 'unknown')}")
    print(f"Architecture: {config.get('architecture', 'unknown')}")

    if args.dry_run:
        print("\n[DRY RUN] Config:")
        print(json.dumps(config, indent=2))
        return

    print("\nTODO: Implement experiment runner")


if __name__ == "__main__":
    main()
