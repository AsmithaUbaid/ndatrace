#!/usr/bin/env python3
"""CLI for scoring NDATrace experiment results."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Score NDATrace experiment results")
    parser.add_argument("--results", required=True, help="Path to results JSONL")
    parser.add_argument("--gold", required=True, help="Path to gold labels")
    args = parser.parse_args()

    print(f"Scoring: {args.results}")
    print(f"Gold: {args.gold}")
    print("\nTODO: Implement evaluation scoring")


if __name__ == "__main__":
    main()
