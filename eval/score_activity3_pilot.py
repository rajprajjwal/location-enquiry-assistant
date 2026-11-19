"""Compare two independent Activity 3 annotation submissions."""

import argparse
import csv
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CASES = {f"P{number:02d}" for number in range(1, 11)}
FIELDS = {"intent": "intents", "api": "apis", "team": "teams"}
TARGET = Fraction(7, 10)


def load_annotations(path, vocab):
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"pilot_id", *FIELDS} <= set(reader.fieldnames or ()):
            raise ValueError(f"{path.name}: expected pilot_id, intent, api and team columns")
        for row in reader:
            case = row["pilot_id"]
            if case not in CASES or case in rows:
                raise ValueError(f"{path.name}: invalid or repeated pilot ID {case!r}")
            for field, key in FIELDS.items():
                value = (row[field] or "").strip()
                if value not in vocab[key]:
                    raise ValueError(f"{path.name}: {case} has an invalid {field}: {value!r}")
                row[field] = value
            sub_intent = (row.get("sub_intent") or "").strip()
            if sub_intent and sub_intent not in vocab["intent_to_sub_intents"][row["intent"]]:
                raise ValueError(f"{path.name}: {case} sub-intent does not belong to its intent")
            escalation = (row.get("should_escalate") or "").strip().lower()
            if escalation not in {"", "true", "false"}:
                raise ValueError(f"{path.name}: {case} should_escalate must be true, false or blank")
            rows[case] = row
    if rows.keys() != CASES:
        raise ValueError(f"{path.name}: missing pilot IDs {', '.join(sorted(CASES - rows.keys()))}")
    return rows


def agreement(first, second):
    total = len(first)
    if not total or total != len(second):
        raise ValueError("agreement requires the same nonzero number of labels from both annotators")
    matches = sum(left == right for left, right in zip(first, second))
    left_counts, right_counts = Counter(first), Counter(second)
    chance = Fraction(sum(count * right_counts[label] for label, count in left_counts.items()), total**2)
    if chance == 1:
        return matches, None
    return matches, (Fraction(matches, total) - chance) / (1 - chance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotator_a", type=Path)
    parser.add_argument("annotator_b", type=Path)
    args = parser.parse_args()
    if args.annotator_a.resolve() == args.annotator_b.resolve():
        parser.error("provide two separately completed annotation files")
    vocab = json.loads((REPO / "vocab/controlled-vocabulary.json").read_text())
    try:
        first = load_annotations(args.annotator_a, vocab)
        second = load_annotations(args.annotator_b, vocab)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    cases = sorted(CASES)
    passed = True
    for field in FIELDS:
        matches, kappa = agreement([first[case][field] for case in cases], [second[case][field] for case in cases])
        score = "undefined" if kappa is None else f"{float(kappa):.3f}"
        meets_target = kappa is not None and kappa >= TARGET
        passed = passed and meets_target
        print(f"{field}: {matches}/{len(cases)} exact agreement, κ={score}, {'PASS' if meets_target else 'RE-PILOT'}")
    for case in cases:
        differences = [f"{field} A={first[case][field]} B={second[case][field]}"
                       for field in FIELDS if first[case][field] != second[case][field]]
        if differences:
            print(f"{case}: {', '.join(differences)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
