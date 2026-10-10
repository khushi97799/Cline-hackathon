"""Seed script: loads scheme + rule JSON from data/schemes/*.json into the DB.

Only reads from data files provided by the operator; never invents data.
Run with: python -m app.seed
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from app.database import SessionLocal, init_db
from app.models import RuleVersion, Scheme
from app.sourcestore import load_source_text
from app.validator import quotes_exist_in_source, validate_schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMES_DIR = ROOT / "data" / "schemes"
RAW_DIR = ROOT / "data" / "raw"

SCHEME_IDS = ["pm-kisan", "pm-ujjwala", "nsap-pension"]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        for scheme_id in SCHEME_IDS:
            scheme_path = SCHEMES_DIR / f"{scheme_id}.json"
            rule_path = SCHEMES_DIR / f"{scheme_id}.rule.json"

            if not scheme_path.exists():
                print(f"Skipping {scheme_id}: missing {scheme_path}")
                continue

            with open(scheme_path, "r", encoding="utf-8") as f:
                scheme_data = json.load(f)

            existing = db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first()
            status = scheme_data.get("status", "draft")
            last_verified = None

            if rule_path.exists():
                with open(rule_path, "r", encoding="utf-8") as f:
                    rule_json = json.load(f)
                validate_schema(rule_json)
                source_text = load_source_text(scheme_id)
                missing = quotes_exist_in_source(rule_json, source_text=source_text)
                if missing:
                    raise ValueError(f"{scheme_id}: quotes not found in source: {missing}")

                if rule_json.get("status") == "approved":
                    status = "approved"
                    last_verified = dt.date.today()

                existing_rv = (
                    db.query(RuleVersion)
                    .filter(RuleVersion.scheme_id == scheme_id, RuleVersion.version == rule_json["version"])
                    .first()
                )
                if not existing_rv:
                    rv = RuleVersion(
                        scheme_id=scheme_id,
                        version=rule_json["version"],
                        status=rule_json.get("status", "draft"),
                        verified=rule_json.get("verified", False),
                        rule_json=rule_json,
                        effective_from=dt.date.fromisoformat(rule_json["effective_from"]),
                        review_by=dt.date.fromisoformat(rule_json["review_by"]),
                    )
                    db.add(rv)

            if existing:
                existing.name = scheme_data["name"]
                existing.benefit = scheme_data["benefit"]
                existing.category = scheme_data.get("category")
                existing.status = status
                existing.data_json = scheme_data
                existing.level, existing.state = scheme_data.get("level"), scheme_data.get("state")
                existing.tags, existing.deadline_json = scheme_data.get("tags"), scheme_data.get("deadline")
                existing.last_verified = last_verified
                db.add(existing)
            else:
                db.add(
                    Scheme(
                        scheme_id=scheme_id,
                        name=scheme_data["name"],
                        benefit=scheme_data["benefit"],
                        category=scheme_data.get("category"),
                        status=status,
                        data_json=scheme_data,
                        level=scheme_data.get("level"), state=scheme_data.get("state"),
                        tags=scheme_data.get("tags"), deadline_json=scheme_data.get("deadline"),
                        last_verified=last_verified,
                    )
                )
            print(f"Seeded {scheme_id} (status={status})")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
