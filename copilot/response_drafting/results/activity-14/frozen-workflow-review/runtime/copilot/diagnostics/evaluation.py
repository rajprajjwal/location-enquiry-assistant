"""Bind human or assistant question judgements to exact prediction and gold files."""
from hashlib import sha256
import json
from pathlib import Path


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def bind_review(predictions, gold, cases, *, reviewer):
    if not reviewer.strip():
        raise ValueError("A reviewer is required.")
    return {"version": "1.0", "predictions_sha256": digest(predictions),
            "gold_sha256": digest(gold), "reviewer": reviewer, "cases": cases}


def score_bound_review(predictions, gold, review):
    if digest(predictions) != review["predictions_sha256"] or digest(gold) != review["gold_sha256"]:
        raise ValueError("Judgements belong to different predictions or gold.")
    rows = [json.loads(line) for line in Path(predictions).read_text().splitlines()]
    labels = json.loads(Path(gold).read_text())["cases"]
    label_by_id = {row["record_id"]: row["questions"] for row in labels}
    if len(label_by_id) != len(labels):
        raise ValueError("Gold record IDs must be unique.")
    reviewed = {row["record_id"]: row["methods"] for row in review["cases"]}
    ids = [row["record_id"] for row in rows]
    if (len(ids) != len(set(ids)) or len(reviewed) != len(review["cases"]) or
            set(ids) != label_by_id.keys() or set(ids) != reviewed.keys()):
        raise ValueError("Provide one judgement for every prediction and gold case.")
    if not rows:
        raise ValueError("No predictions.")
    methods = set(rows[0]["questions"])
    totals = {method: {"predicted": 0, "gold": 0, "matches": 0, "facts": 0,
                       "gold_facts": 0, "questions_on_empty_gold": 0} for method in methods}
    for row in rows:
        expected = label_by_id[row["record_id"]]
        if set(row["questions"]) != methods or set(reviewed[row["record_id"]]) != methods:
            raise ValueError("Method sets differ.")
        if row.get("gold", expected) != expected:
            raise ValueError("Embedded gold differs from locked labels.")
        for method in methods:
            actual = row["questions"][method]
            decision = reviewed[row["record_id"]][method]
            whole, facts = decision["whole"], decision["facts"]
            if len(whole) != len({tuple(pair) for pair in whole}) or len(facts) != len({tuple(triple) for triple in facts}):
                raise ValueError("Duplicate matches.")
            if len(whole) != len({pair[0] for pair in whole}) or len(whole) != len({pair[1] for pair in whole}):
                raise ValueError("Whole-question matches must be one-to-one.")
            if any(type(p) is not int or type(g) is not int or not 1 <= p <= len(actual)
                   or not 1 <= g <= len(expected) for p, g in whole):
                raise ValueError("Invalid whole-question index.")
            if any(any(type(index) is not int for index in (p, g, f)) or not 1 <= p <= len(actual)
                   or not 1 <= g <= len(expected) or not 1 <= f <= len(expected[g-1]["facts"])
                   for p, g, f in facts):
                raise ValueError("Invalid atomic-fact index.")
            covered = set(map(tuple, facts))
            if any((p, g, f) not in covered for p, g in whole for f in range(1, len(expected[g-1]["facts"]) + 1)):
                raise ValueError("Whole-question match lacks all required facts.")
            total = totals[method]
            total["predicted"] += len(actual)
            total["gold"] += len(expected)
            total["matches"] += len(whole)
            total["facts"] += len({(g, f) for _, g, f in facts})
            total["gold_facts"] += sum(len(question["facts"]) for question in expected)
            total["questions_on_empty_gold"] += len(actual) if not expected else 0
    return {
        method: {**total,
                 "f1": 2 * total["matches"] / (total["predicted"] + total["gold"]) if total["predicted"] + total["gold"] else 0,
                 "precision": total["matches"] / total["predicted"] if total["predicted"] else 0,
                 "recall": total["matches"] / total["gold"] if total["gold"] else 0,
                 "fact_recall": total["facts"] / total["gold_facts"] if total["gold_facts"] else 0}
        for method, total in totals.items()
    }
