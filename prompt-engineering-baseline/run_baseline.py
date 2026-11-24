"""Run the three isolated prompt strategies through the shared model gateway."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True)
    parser.add_argument('--workflow', choices=['sales','support'], default='support')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent/'.env')
    from app.baseline.prompting import run_baseline
    result = run_baseline(args.query, args.workflow)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text+'\n')
    print(text)
    if all(strategy.get('failure') for strategy in result['strategies']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
