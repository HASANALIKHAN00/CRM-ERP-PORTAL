"""
BoxTech ERPNext -> Reporting DB sync service.
Idempotent: uses modified >= last_sync_time to fetch only changed
records; upserts by primary key so re-running never duplicates.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
import models
import erpnext_client
from sync_config import SYNC_CONFIG


def get_last_sync_time(db: Session) -> str | None:
    last_run = db.query(func.max(models.SyncRun.completed_at)).filter(
        models.SyncRun.result == "success"
    ).scalar()
    if last_run is None:
        return None  # first run ever -> full import, no filter
    return last_run.strftime("%Y-%m-%d %H:%M:%S")


def convert_value(raw_value, column):
    """Minimal type coercion for values coming back as JSON from the API."""
    if raw_value in (None, ""):
        return None
    col_type = str(column.type)
    try:
        if "BOOLEAN" in col_type:
            return bool(int(raw_value)) if not isinstance(raw_value, bool) else raw_value
        return raw_value
    except (ValueError, TypeError):
        return None


def sync_doctype(db: Session, config: dict, since: str | None) -> dict:
    doctype = config["doctype"]
    model = config["model"]
    field_map = config["field_map"]
    pk_reporting = config["pk_reporting"]

    filters = [["modified", ">=", since]] if since else None
    erpnext_fields = list(field_map.keys())

    records = erpnext_client.get_records(
        doctype, filters=filters, fields=erpnext_fields, page_size=500,
        parent=config.get("parent_doctype")
    )

    inserted, updated, rejected = 0, 0, 0
    errors = []

    for record in records:
        try:
            mapped = {}
            for erpnext_field, reporting_field in field_map.items():
                column = model.__table__.columns.get(reporting_field)
                mapped[reporting_field] = convert_value(record.get(erpnext_field), column)

            match_field = config.get("match_field", pk_reporting)
            match_value = mapped[match_field]
            existing = db.query(model).filter_by(**{match_field: match_value}).first()

            if existing:
                for field, value in mapped.items():
                    setattr(existing, field, value)
                updated += 1
            else:
                db.add(model(**mapped))
                inserted += 1

            db.flush()

        except Exception as e:
            rejected += 1
            errors.append({"record_id": record.get("name", "unknown"), "error": str(e)})
            db.rollback()

    db.commit()
    return {
        "doctype": doctype,
        "processed": len(records),
        "inserted": inserted,
        "updated": updated,
        "rejected": rejected,
        "errors": errors,
    }


def run_sync():
    db = SessionLocal()
    started_at = datetime.now(timezone.utc)
    sync_run = models.SyncRun(
        started_at=started_at,
        result="running",
        records_processed=0, records_inserted=0, records_updated=0,
        records_skipped=0, records_rejected=0, retry_count=0,
    )
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    # NOTE: deliberately always doing a full pull per table rather than
    # inferring full-vs-incremental from local row counts. That heuristic
    # is fragile \u2014 it can't distinguish "fully synced" from "partially
    # synced due to an earlier bug/interruption." Given confirmed real
    # data volumes here (largest table ~2,500 rows), a full pull every
    # run is cheap and removes an entire class of silent under-sync bugs.
    # Idempotent upserts make this safe: unchanged rows just update
    # in-place, never duplicate. Revisit if/when data volume grows
    # enough that this becomes a real bandwidth concern.
    print("Sync started. Full pull per table (idempotent upsert).")

    totals = {"processed": 0, "inserted": 0, "updated": 0, "rejected": 0}
    any_errors = False

    for config in SYNC_CONFIG:
        doctype = config["doctype"]
        print(f"  Syncing {doctype}...")
        try:
            result = sync_doctype(db, config, since=None)
            print(f"    {result['processed']} processed, {result['inserted']} inserted, "
                  f"{result['updated']} updated, {result['rejected']} rejected")

            for field in ["processed", "inserted", "updated", "rejected"]:
                totals[field] += result[field]

            for err in result["errors"]:
                any_errors = True
                db.add(models.SyncError(
                    sync_run_id=sync_run.id,
                    doctype=doctype,
                    record_id=err["record_id"],
                    error_message=str(err["error"])[:2000],
                    occurred_at=datetime.now(timezone.utc),
                ))
            db.commit()

        except Exception as e:
            any_errors = True
            print(f"    FAILED entirely: {e}")
            db.rollback()
            db.add(models.SyncError(
                sync_run_id=sync_run.id,
                doctype=doctype,
                record_id="N/A",
                error_message=str(e)[:2000],
                occurred_at=datetime.now(timezone.utc),
            ))
            db.commit()

    sync_run.completed_at = datetime.now(timezone.utc)
    sync_run.result = "partial" if any_errors else "success"
    sync_run.records_processed = totals["processed"]
    sync_run.records_inserted = totals["inserted"]
    sync_run.records_updated = totals["updated"]
    sync_run.records_rejected = totals["rejected"]
    db.commit()

    print(f"Sync complete. Result: {sync_run.result}. "
          f"Totals: {totals['inserted']} inserted, {totals['updated']} updated, {totals['rejected']} rejected.")
    db.close()


if __name__ == "__main__":
    run_sync()