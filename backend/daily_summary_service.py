import os
from datetime import date
from openai import OpenAI
from database import SessionLocal
import query_functions
import models

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-5.5"

# The fixed set of metrics that make up the daily digest. Deliberately
# curated rather than "all 31 functions" — a daily summary should read
# like a briefing, not a data dump. Add/remove entries here to change
# what the summary covers; nothing else needs to change.
METRICS_TO_INCLUDE = [
    ("total_sales_value_this_month", lambda db: query_functions.get_total_sales_value(db, this_month=True, role="admin")),
    ("new_leads_this_month", lambda db: query_functions.get_new_leads_this_month(db, role="admin")),
    ("stale_customers", lambda db: query_functions.get_stale_customers(db, days=7, role="admin")),
    ("calls_today", lambda db: query_functions.get_calls_today(db, role="admin")),
    ("team_performance_this_month", lambda db: query_functions.get_team_performance_summary(db, this_month=True, role="admin")),
    ("customers_with_pending_payments", lambda db: query_functions.get_customers_with_pending_payments(db, role="admin")),
]

SUMMARY_SYSTEM_PROMPT = (
    "You are writing a short daily business briefing for BoxTech's leadership. "
    "You will be given real, already-retrieved metrics below \u2014 do not invent "
    "or estimate any number not present in this data. Write 3-5 short paragraphs "
    "covering: overall sales performance this month, any notable risks or items "
    "needing attention (stale customers, pending payments), and team activity. "
    "Be direct and factual, not promotional. If a metric shows zero or no data, "
    "say so plainly rather than skipping it."
)


def gather_metrics(db) -> dict:
    metrics = {}
    for key, fn in METRICS_TO_INCLUDE:
        try:
            metrics[key] = fn(db)
        except Exception as e:
            metrics[key] = {"error": str(e)}
    return metrics


def generate_summary_text(metrics: dict) -> str:
    import json
    context_lines = []
    for key, result in metrics.items():
        summary_text = result.get("summary", "no data")
        records = result.get("records") or []
        # Cap how many records get embedded per metric, so one large
        # result (e.g. 137 stale customers) doesn't blow out the prompt
        # or drown out the other metrics.
        truncated = records[:15]
        records_json = json.dumps(truncated, default=str) if truncated else "[]"
        note = f" (showing first {len(truncated)} of {len(records)})" if len(records) > len(truncated) else ""
        context_lines.append(f"{key}: {summary_text}\n  records{note}: {records_json}")
    context = "\n\n".join(context_lines)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Today's retrieved metrics:\n\n{context}"},
        ],
    )
    return response.choices[0].message.content


def run_daily_summary(send_email: bool = True) -> dict:
    """
    Generates today's summary, stores it, and optionally emails it.
    Safe to call more than once a day (e.g. for manual testing) \u2014
    each call creates a new row rather than overwriting.
    """
    db = SessionLocal()
    try:
        metrics = gather_metrics(db)
        content = generate_summary_text(metrics)

        record = models.DailySummary(
            summary_date=date.today(),
            content=content,
            metrics=metrics,
            email_sent=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        if send_email:
            from email_sender import send_summary_email
            try:
                send_summary_email(content, record.summary_date)
                record.email_sent = True
                db.commit()
            except Exception as e:
                print(f"Email send failed (summary still saved): {e}")

        return {"id": str(record.id), "content": content, "email_sent": record.email_sent}
    finally:
        db.close()


if __name__ == "__main__":
    # send_email explicitly False until SMTP is configured (email_sender.py
    # doesn't exist yet) -- flip to True once that's wired up.
    result = run_daily_summary(send_email=False)
    print(result["content"])
