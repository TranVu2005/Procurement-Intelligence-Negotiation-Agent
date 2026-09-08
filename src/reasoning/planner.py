"""Reasoning module — task decomposition, re-plan.

Owner: Nguoi B
Plan format contract (see PROJECT-SETUP.md section 5):
{
    "steps": [
        {"action": str, "params": dict, "reason": str},
        ...
    ]
}
"""


def make_plan(state: dict) -> dict:
    raise NotImplementedError
