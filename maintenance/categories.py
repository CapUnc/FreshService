"""Utilities for exporting and reviewing Freshservice ticket categories."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from dotenv import load_dotenv


def load_environment(env_path: str = "api.env") -> None:
    """Load environment variables, preferring api.env when present."""
    load_dotenv(env_path) or load_dotenv()


def fetch_ticket_fields(domain: str, api_key: str, *, timeout: float = 30.0) -> List[dict]:
    """Retrieve ticket form fields from Freshservice."""
    url = f"https://{domain}/api/v2/ticket_form_fields"
    response = requests.get(url, auth=(api_key, "X"), timeout=timeout)
    response.raise_for_status()
    payload = response.json() or {}
    return payload.get("ticket_fields", []) or []


def extract_category_hierarchy(fields: List[dict]) -> Dict[str, Dict[str, List[str]]]:
    """Transform Freshservice nested dropdown data into a simple hierarchy."""
    category_tree: Dict[str, Dict[str, List[str]]] = {}

    for field in fields:
        if field.get("field_type") != "nested_dropdown":
            continue
        if (field.get("label") or "").strip().lower() != "category":
            continue

        for category in field.get("nested_ticket_fields", []):
            category_name = category.get("name", "Unknown")
            sub_map: Dict[str, List[str]] = {}
            for sub in category.get("sub_fields", []):
                sub_name = sub.get("name", "Unknown")
                items = [item.get("name", "Unknown") for item in sub.get("sub_fields", [])]
                sub_map[sub_name] = items
            category_tree[category_name] = sub_map

    return category_tree


def write_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def refresh_categories(
    *,
    domain: str,
    api_key: str,
    output_path: Path,
    raw_path: Path | None,
    timeout: float,
) -> Tuple[int, int]:
    """Fetch Freshservice categories and write them to disk.

    Returns a tuple of (category_count, subcategory_count).
    """
    fields = fetch_ticket_fields(domain, api_key, timeout=timeout)
    if raw_path:
        write_json(fields, raw_path)

    hierarchy = extract_category_hierarchy(fields)
    write_json(hierarchy, output_path)

    sub_count = sum(len(subs) for subs in hierarchy.values())
    return len(hierarchy), sub_count


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Freshservice ticket categories to JSON."
    )
    parser.add_argument(
        "--output",
        default="categories.json",
        help="Path for the simplified category hierarchy (default: categories.json)",
    )
    parser.add_argument(
        "--raw",
        default="raw_ticket_fields.json",
        help="Optional path to store the raw ticket field payload (default: raw_ticket_fields.json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--domain",
        help="Override Freshservice domain (otherwise sourced from environment)",
    )
    parser.add_argument(
        "--api-key",
        help="Override Freshservice API key (otherwise sourced from environment)",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Skip writing the raw ticket field JSON payload.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    load_environment()
    args = parse_args(argv)

    domain = (args.domain or os.getenv("FRESHSERVICE_DOMAIN") or "").strip()
    api_key = (args.api_key or os.getenv("FRESHSERVICE_API_KEY") or "").strip()

    if not domain or not api_key:
        print("❌ FRESHSERVICE_DOMAIN and FRESHSERVICE_API_KEY must be provided.")
        return 1

    output_path = Path(args.output).expanduser().resolve()
    raw_path = None if args.no_raw else Path(args.raw).expanduser().resolve()

    try:
        categories, subcategories = refresh_categories(
            domain=domain,
            api_key=api_key,
            output_path=output_path,
            raw_path=raw_path,
            timeout=args.timeout,
        )
    except requests.HTTPError as http_err:
        print(f"❌ HTTP error: {http_err.response.status_code} {http_err.response.text[:200]}")
        return 1
    except Exception as exc:
        print(f"❌ Failed to refresh categories: {exc}")
        return 1

    print(f"✅ Wrote category hierarchy to {output_path}")
    if raw_path:
        print(f"📄 Raw ticket field payload stored at {raw_path}")
    print(f"📊 Categories: {categories} · Subcategories: {subcategories}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
