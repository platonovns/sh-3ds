"""List or inspect unprocessed uploaded sessions; marking requires an evidence file."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'dev_server'))
from hardware_reports import read_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=PORT / 'reports/incoming-hardware')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--mark-processed', metavar='REPORT_TXT')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    if args.mark_processed:
        if Path(args.mark_processed).name != args.mark_processed or not args.evidence or not args.evidence.is_file():
            parser.error('use a report filename and an existing --evidence file')
        receipt = read_receipt(root / (args.mark_processed + '.json'))
        evidence = args.evidence.resolve()
        if receipt['sha256'].encode('ascii') not in evidence.read_bytes():
            parser.error('the evidence file must cite the raw report SHA-256')
        marker = root / 'processed' / (args.mark_processed + '.json')
        marker.parent.mkdir(parents=True, exist_ok=True)
        with marker.open('x', encoding='utf-8') as out:
            json.dump(dict(report_sha256=receipt['sha256'], evidence=str(evidence),
                           evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                           processed_utc=datetime.now(timezone.utc).isoformat()), out, indent=2)
            out.write('\n')
        print(marker)
        return
    results = []
    for path in sorted(root.glob('*.txt.json')):
        if not args.all and (root / 'processed' / path.name).exists():
            continue
        try:
            results.append(read_receipt(path))
        except (ValueError, OSError, KeyError) as error:
            results.append(dict(receipt=path.name, error=str(error)))
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
