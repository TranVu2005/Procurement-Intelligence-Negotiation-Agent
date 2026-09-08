"""Chay AutoEval, xuat toi thieu 5 chi so:
Task Success Rate, Constraint Satisfaction Rate, Tool Call Success Rate,
Citation/Evidence Correctness, Failure Recovery Rate.
"""

import argparse
import json


def load_cases(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", required=True)
    args = parser.parse_args()

    cases = load_cases(args.eval_set)
    raise NotImplementedError(f"Chay {len(cases)} case qua agent.py sau khi agent san sang")


if __name__ == "__main__":
    main()
