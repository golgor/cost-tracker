"""Import expenses from a cost-split-dump.json file into the cost-tracker API.

Usage:
    uv run scripts/import_cost_split.py [OPTIONS]

Options:
    --dump-file   Path to the JSON dump file (default: cost-split-dump.json)
    --api-url     Base URL of the API (default: http://localhost:8000)
    --api-key     Bearer token (default: $GLANCE_API_KEY env var)
    --user1-id    New system user ID for old user_id=1 (default: 1)
    --user2-id    New system user ID for old user_id=2 (default: 2)
    --dry-run     Print what would be sent without actually posting

Field mapping from dump → new API:
    location + description → description  (combined if description is non-empty)
    date (ISO timestamp)   → date         (YYYY-MM-DD, date part only)
    amount                 → amount
    user_id                → creator_id, payer_id  (same person entered and paid)
    both user IDs          → member_ids   (always split between both users)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import cost-split dump into cost-tracker API")
    parser.add_argument("--dump-file", default="cost-split-dump.json", help="Path to JSON dump")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default=None, help="Bearer API key (or set GLANCE_API_KEY)")
    parser.add_argument("--user1-id", type=int, default=1, help="New system user ID for old user_id=1")
    parser.add_argument("--user2-id", type=int, default=2, help="New system user ID for old user_id=2")
    parser.add_argument("--dry-run", action="store_true", help="Print requests without posting")
    return parser.parse_args()


def build_description(location: str, description: str) -> str:
    """Combine location and description into a single description field."""
    location = location.strip()
    description = description.strip()
    if description:
        return f"{location} – {description}"
    return location


def parse_date(iso_timestamp: str) -> str:
    """Extract YYYY-MM-DD from an ISO 8601 timestamp, adjusting for UTC offset.

    The dump stores dates as UTC timestamps (e.g. '2025-06-29T22:00:00.000Z').
    These represent local midnight in UTC+2 (CEST), so we add 2 hours before
    extracting the date to get the correct local date.
    """
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    # Adjust to local time (UTC+2 / Vienna) to recover the original date
    from datetime import timedelta
    local_dt = dt.astimezone(timezone(timedelta(hours=2)))
    return local_dt.date().isoformat()


def map_user_id(old_id: int, user1_id: int, user2_id: int) -> int:
    if old_id == 1:
        return user1_id
    if old_id == 2:
        return user2_id
    raise ValueError(f"Unexpected user_id in dump: {old_id}")


def build_payload(entry: dict, user1_id: int, user2_id: int) -> dict:
    payer = map_user_id(entry["user_id"], user1_id, user2_id)
    return {
        "amount": str(Decimal(str(entry["amount"])).quantize(Decimal("0.01"))),
        "description": build_description(entry["location"], entry.get("description", "")),
        "date": parse_date(entry["date"]),
        "creator_id": payer,
        "payer_id": payer,
        "member_ids": [user1_id, user2_id],
        "currency": "EUR",
        "split_type": "EVEN",
    }


def main() -> None:
    args = parse_args()

    api_key = args.api_key or os.environ.get("GLANCE_API_KEY")
    if not api_key:
        print("Error: provide --api-key or set GLANCE_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    dump_path = Path(args.dump_file)
    if not dump_path.exists():
        print(f"Error: dump file not found: {dump_path}", file=sys.stderr)
        sys.exit(1)

    entries = json.loads(dump_path.read_text())
    print(f"Loaded {len(entries)} entries from {dump_path}")

    if args.dry_run:
        print("\n--- DRY RUN — no requests will be sent ---\n")
        for i, entry in enumerate(entries, 1):
            payload = build_payload(entry, args.user1_id, args.user2_id)
            print(f"[{i:3d}] {payload}")
        return

    import httpx

    url = f"{args.api_url.rstrip('/')}/api/v1/expenses"
    headers = {"Authorization": f"Bearer {api_key}"}

    succeeded = 0
    failed = 0

    with httpx.Client(timeout=30) as client:
        for i, entry in enumerate(entries, 1):
            payload = build_payload(entry, args.user1_id, args.user2_id)
            try:
                response = client.post(url, json=payload, headers=headers)
                if response.status_code == 201:
                    expense_id = response.json().get("id", "?")
                    print(f"[{i:3d}] ✓  id={expense_id}  {payload['date']}  {payload['description'][:50]}")
                    succeeded += 1
                else:
                    print(
                        f"[{i:3d}] ✗  HTTP {response.status_code}  "
                        f"{payload['description'][:40]}  → {response.text[:120]}"
                    )
                    failed += 1
            except httpx.RequestError as e:
                print(f"[{i:3d}] ✗  Request error: {e}")
                failed += 1

    print(f"\nDone: {succeeded} imported, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
