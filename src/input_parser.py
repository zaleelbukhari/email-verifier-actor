"""
Email Verifier Pro — Input Parser

Handles all supported input formats:
1. Direct email list (JSON string array via Apify input)
2. CSV file from URL (with auto-detection of email column)
3. Existing Apify dataset (by dataset ID)

Validates email format and deduplicates.
"""

import csv
import io
import re

import aiohttp

from apify import Actor


# Common column names for email fields (case-insensitive matching)
EMAIL_COLUMN_NAMES = {
    "email", "e-mail", "email_address", "emailaddress",
    "email address", "mail", "e_mail", "contact_email",
    "user_email", "primary_email", "work_email",
    "personal_email", "emails", "recipient",
}

# Basic email regex — catches obviously invalid formats
# Real validation happens via SMTP in the verifier
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def validate_email_format(email: str) -> bool:
    """Check if an email address has valid syntax."""
    if not email or len(email) > 254:
        return False
    return EMAIL_REGEX.match(email) is not None


async def parse_input(actor_input: dict) -> list[dict]:
    """
    Parse emails from the actor input.

    Supports three input methods (checked in this order):
    1. Direct email list in the 'emails' field
    2. CSV file URL in the 'csvUrl' field
    3. Apify dataset ID in the 'datasetId' field

    Returns a list of dictionaries (rows) with a special '__email__' key containing the raw email string.
    """
    emails = []

    # Method 1: Direct email list
    direct_emails = actor_input.get("emails", [])
    if direct_emails and isinstance(direct_emails, list):
        # Filter out empty strings and non-strings
        valid = [
            str(e).strip() for e in direct_emails
            if e and str(e).strip()
        ]
        if valid:
            Actor.log.info(f"📋 Found {len(valid)} emails from direct input")
            emails.extend([{"email": e, "__email__": e} for e in valid])

    # Method 2: CSV file URL
    csv_url = actor_input.get("csvUrl", "").strip()
    if csv_url:
        csv_emails = await _parse_csv_url(
            csv_url,
            actor_input.get("emailColumn", ""),
        )
        if csv_emails:
            Actor.log.info(f"📋 Found {len(csv_emails)} emails from CSV URL")
            emails.extend(csv_emails)

    # Method 3: Apify dataset
    dataset_id = actor_input.get("datasetId", "").strip()
    if dataset_id:
        ds_emails = await _parse_dataset(
            dataset_id,
            actor_input.get("emailColumn", ""),
        )
        if ds_emails:
            Actor.log.info(f"📋 Found {len(ds_emails)} emails from dataset")
            emails.extend(ds_emails)

    if not emails:
        raise ValueError(
            "No emails found in input. Please provide emails using at least one method: "
            "paste them directly, provide a CSV URL, or link an Apify dataset ID."
        )

    return emails


async def _parse_csv_url(url: str, email_column: str = "") -> list[dict]:
    """Download and parse a CSV file from a URL."""
    # Auto-convert Google Sheets sharing links to CSV export links (massive UX win)
    if "docs.google.com/spreadsheets" in url and "/edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
        Actor.log.info(f"✨ Auto-converted Google Sheets link to CSV download format")

    Actor.log.info(f"📥 Downloading CSV from: {url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    raise ValueError(
                        f"Failed to download CSV: HTTP {resp.status}. "
                        f"Make sure the URL is publicly accessible."
                    )

                content_type = resp.headers.get("Content-Type", "")
                text = await resp.text()

    except aiohttp.ClientError as e:
        raise ValueError(
            f"Failed to download CSV from URL: {str(e)}. "
            f"Make sure the URL is correct and publicly accessible."
        ) from e

    if not text.strip():
        raise ValueError("CSV file is empty.")

    # Friendly error for common mistake: pasting a web page URL instead of a raw CSV URL
    if "<html" in text.lower()[:500] or "<!doctype html" in text.lower()[:500]:
        raise ValueError(
            "The provided URL returned an HTML web page instead of a CSV file. "
            "If you are using Google Sheets, make sure to use File -> Share -> Publish to Web (as CSV), "
            "or change the end of your URL from '/edit' to '/export?format=csv'."
        )

    return _extract_emails_from_csv(text, email_column)


async def _parse_dataset(dataset_id: str, email_column: str = "") -> list[dict]:
    """Read emails from an existing Apify dataset."""
    Actor.log.info(f"📥 Reading from Apify dataset: {dataset_id}")

    try:
        dataset = await Actor.open_dataset(id=dataset_id)
        data = await dataset.get_data()
        items = data.items if hasattr(data, "items") else []
    except Exception as e:
        raise ValueError(
            f"Failed to read dataset '{dataset_id}': {str(e)}. "
            f"Make sure the dataset ID is correct and accessible."
        ) from e

    if not items:
        raise ValueError(f"Dataset '{dataset_id}' is empty or not found.")

    # Find the email column
    column = _find_email_column(items[0], email_column)
    if not column:
        available = ", ".join(items[0].keys()) if items else "none"
        raise ValueError(
            f"Could not find an email column in the dataset. "
            f"Available columns: {available}. "
            f"Please specify the column name in the 'Email Column Name' field."
        )

    emails = []
    for item in items:
        val = item.get(column, "")
        if val and isinstance(val, str) and val.strip():
            row_dict = dict(item)
            row_dict["__email__"] = val.strip()
            emails.append(row_dict)

    Actor.log.info(f"Found email column: '{column}' ({len(emails)} emails)")
    return emails


def _extract_emails_from_csv(text: str, email_column: str = "") -> list[dict]:
    """Extract emails from CSV text content."""
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValueError(
            "CSV file has no headers. The first row must contain column names."
        )

    # Find the email column
    column = _find_email_column(
        {f: "" for f in reader.fieldnames}, email_column
    )

    if not column:
        available = ", ".join(reader.fieldnames)
        raise ValueError(
            f"Could not auto-detect the email column in the CSV. "
            f"Available columns: {available}. "
            f"Please specify the column name in the 'Email Column Name' field."
        )

    Actor.log.info(f"Using email column: '{column}'")

    emails = []
    for row in reader:
        val = row.get(column, "")
        if val and val.strip():
            row_dict = dict(row)
            row_dict["__email__"] = val.strip()
            emails.append(row_dict)

    return emails


def _find_email_column(sample_row: dict, user_specified: str = "") -> str | None:
    """
    Find the email column in a dict of column names.

    Priority:
    1. User-specified column name (exact match, case-insensitive)
    2. Auto-detect from common email column names
    3. First column containing '@' in its values
    """
    columns = list(sample_row.keys())

    # Priority 1: User-specified
    if user_specified:
        user_lower = user_specified.strip().lower()
        for col in columns:
            if col.strip().lower() == user_lower:
                return col
        # Try partial match
        for col in columns:
            if user_lower in col.strip().lower():
                return col
        return None

    # Priority 2: Auto-detect from common names
    for col in columns:
        if col.strip().lower() in EMAIL_COLUMN_NAMES:
            return col

    # Priority 3: Column containing '@' in name
    for col in columns:
        if "@" in str(sample_row.get(col, "")):
            return col

    # Priority 4: Single-column CSV (likely just emails)
    if len(columns) == 1:
        return columns[0]

    return None
