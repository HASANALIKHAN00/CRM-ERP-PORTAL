"""
Diagnostic: tests every field in every SYNC_CONFIG entry against the
real ERPNext API to find permission gaps in one pass, rather than
hitting them one at a time during actual sync runs.
"""
import json
import requests
from sync_config import SYNC_CONFIG
from erpnext_client import ERPNEXT_URL, HEADERS


def check_field(doctype: str, field: str) -> str | None:
    """Returns None if the field is queryable, or the error message if not."""
    params = {
        "limit_page_length": 1,
        "fields": json.dumps([field]),
    }
    response = requests.get(
        f"{ERPNEXT_URL}/api/resource/{doctype}",
        headers=HEADERS,
        params=params,
    )
    if response.status_code >= 400:
        try:
            exc = response.json().get("exception", response.text[:200])
            # Trim to just the meaningful part, e.g. "...DataError: Field not permitted in query: source"
            return exc.split("\n")[0]
        except Exception:
            return response.text[:200]
    return None


def main():
    print("Checking every field across all SYNC_CONFIG entries...\n")
    total_checked = 0
    problems = {}

    for config in SYNC_CONFIG:
        doctype = config["doctype"]
        fields = list(config["field_map"].keys())
        # 'name' is always queryable (it's the primary key), skip to save calls
        fields_to_check = [f for f in fields if f != "name"]

        bad_fields = []
        for field in fields_to_check:
            total_checked += 1
            error = check_field(doctype, field)
            if error:
                bad_fields.append((field, error))

        if bad_fields:
            problems[doctype] = bad_fields
            print(f"[{doctype}] {len(bad_fields)} problem field(s):")
            for field, error in bad_fields:
                print(f"    {field}: {error}")
        else:
            print(f"[{doctype}] OK \u2014 all {len(fields_to_check)} field(s) queryable")

    print(f"\nChecked {total_checked} fields across {len(SYNC_CONFIG)} DocTypes.")
    if problems:
        print(f"\n{sum(len(v) for v in problems.values())} field(s) across {len(problems)} DocType(s) need attention.")
    else:
        print("\nAll fields queryable \u2014 no permission gaps found.")


if __name__ == "__main__":
    main()