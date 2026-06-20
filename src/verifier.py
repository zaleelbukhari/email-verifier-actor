"""
Email Verifier Pro — Reacher API Client

Handles communication with the self-hosted Reacher email verification API.
Includes retry logic with exponential backoff for temporary SMTP failures.
"""

import asyncio
import time
from datetime import datetime, timezone

import aiohttp

from apify import Actor


# ── Reacher API Configuration ──
REACHER_URL = "http://193.181.213.12:8080/v0/check_email"
REACHER_API_KEY = "my-secret-key-123"

# Map Reacher's is_reachable values to user-friendly status labels
STATUS_MAP = {
    "safe": "valid",
    "invalid": "invalid",
    "risky": "risky",
    "unknown": "unknown",
}


async def create_session(timeout: int = 30) -> aiohttp.ClientSession:
    """Create an aiohttp session with appropriate timeout settings."""
    connector = aiohttp.TCPConnector(
        limit=20,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )
    client_timeout = aiohttp.ClientTimeout(
        total=timeout + 10,  # Buffer above the Reacher timeout
        connect=10,
        sock_read=timeout + 5,
    )
    session = aiohttp.ClientSession(
        connector=connector,
        timeout=client_timeout,
        headers={
            "Content-Type": "application/json",
            "x-reacher-secret": REACHER_API_KEY,
        },
    )
    return session


async def close_session(session: aiohttp.ClientSession) -> None:
    """Gracefully close the aiohttp session."""
    if session and not session.closed:
        await session.close()
        # Allow time for SSL connections to close
        await asyncio.sleep(0.25)


async def verify_email(
    session: aiohttp.ClientSession,
    email: str,
    max_retries: int = 2,
    timeout: int = 30,
) -> dict:
    """
    Verify a single email address via the Reacher API.

    Retries with exponential backoff on temporary failures.
    Returns a standardized result dict regardless of success/failure.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await _call_reacher(session, email)
            return _parse_response(email, result)

        except aiohttp.ClientResponseError as e:
            last_error = f"HTTP {e.status}: {e.message}"
            if e.status == 429:
                # Rate limited — always retry with longer backoff
                backoff = min(2 ** (attempt + 2), 30)
                Actor.log.warning(
                    f"Rate limited on {email}, retrying in {backoff}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(backoff)
                continue
            elif e.status >= 500:
                # Server error — retry
                backoff = min(2 ** attempt, 10)
                Actor.log.warning(
                    f"Server error on {email}: {e.status}, retrying in {backoff}s"
                )
                await asyncio.sleep(backoff)
                continue
            else:
                # Client error (4xx) — don't retry
                break

        except asyncio.TimeoutError:
            last_error = f"Timeout after {timeout}s"
            if attempt < max_retries:
                backoff = min(2 ** attempt, 10)
                Actor.log.warning(
                    f"Timeout verifying {email}, retrying in {backoff}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(backoff)
                continue

        except aiohttp.ClientError as e:
            last_error = f"Connection error: {str(e)}"
            if attempt < max_retries:
                backoff = min(2 ** attempt, 10)
                Actor.log.warning(
                    f"Connection error on {email}: {e}, retrying in {backoff}s"
                )
                await asyncio.sleep(backoff)
                continue

        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            Actor.log.exception(f"Unexpected error verifying {email}: {e}")
            break

    # All retries exhausted — return error result
    return _error_result(email, last_error or "Unknown error")


async def _call_reacher(
    session: aiohttp.ClientSession,
    email: str,
) -> dict:
    """Make a single API call to Reacher."""
    payload = {
        "to_email": email,
        "from_email": "verify@skipthelnes.info",
        "hello_name": "skipthelnes.info",
    }

    async with session.post(REACHER_URL, json=payload) as resp:
        resp.raise_for_status()
        return await resp.json()


def _parse_response(email: str, data: dict) -> dict:
    """Parse Reacher's JSON response into a standardized output format."""
    try:
        is_reachable = data.get("is_reachable", "unknown")
        status = STATUS_MAP.get(is_reachable, "unknown")

        # Extract sub-check results
        misc = data.get("misc", {})
        mx = data.get("mx", {})
        smtp = data.get("smtp", {})
        syntax = data.get("syntax", {})

        # Determine MX host
        mx_records = mx.get("records", [])
        mx_host = mx_records[0] if mx_records else ""
        # Clean MX host (remove trailing dot)
        if isinstance(mx_host, str) and mx_host.endswith("."):
            mx_host = mx_host[:-1]

        # Determine SMTP response message
        smtp_desc = ""
        if isinstance(smtp, dict):
            if smtp.get("can_connect_smtp", False):
                if smtp.get("is_deliverable", False):
                    smtp_desc = "250 OK — Mailbox exists"
                elif smtp.get("is_disabled", False):
                    smtp_desc = "Mailbox disabled"
                else:
                    smtp_desc = "SMTP connected but mailbox not confirmed"
            else:
                smtp_desc = "Could not connect to SMTP server"

            # Check for specific error
            smtp_error = smtp.get("error", None)
            if smtp_error and isinstance(smtp_error, dict):
                error_type = smtp_error.get("type", "")
                error_msg = smtp_error.get("message", "")
                if error_type or error_msg:
                    smtp_desc = f"{error_type}: {error_msg}".strip(": ")

        # Determine if catch-all with confirmed deliverability
        is_catch_all = smtp.get("is_catch_all", False) if isinstance(smtp, dict) else False
        is_deliverable = smtp.get("is_deliverable", False) if isinstance(smtp, dict) else False
        can_connect = smtp.get("can_connect_smtp", False) if isinstance(smtp, dict) else False

        # Reclassify: catch-all domains with confirmed SMTP deliverability
        # are almost always valid in practice
        is_role_account = misc.get("is_role_account", False)
        if is_reachable == "risky" and is_catch_all and is_deliverable and can_connect:
            status = "valid"
            confidence = "medium"
        elif is_reachable == "risky" and is_role_account and is_deliverable and can_connect and not misc.get("is_disposable", False):
            # Role-based emails (info@, admin@) at real domains are valid
            # addresses — just flag them so users can decide
            status = "valid"
            confidence = "medium"
        elif is_reachable == "safe":
            confidence = "high"
        elif is_reachable == "invalid":
            confidence = "high"
        else:
            confidence = "low"

        return {
            "email": email,
            "status": status,
            "confidence": confidence,
            "is_reachable": is_reachable,
            "is_disposable": misc.get("is_disposable", False),
            "is_role_based": misc.get("is_role_account", False),
            "is_catch_all": is_catch_all,
            "is_free_provider": misc.get("is_free", False),
            "syntax_valid": syntax.get("is_valid_syntax", True),
            "mx_exists": len(mx_records) > 0,
            "smtp_reachable": can_connect,
            "mx_host": mx_host,
            "smtp_response": smtp_desc,
            "error_message": "",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        Actor.log.warning(f"Failed to parse response for {email}: {e}")
        return _error_result(email, f"Parse error: {str(e)}")


def _error_result(email: str, error_message: str) -> dict:
    """Create an error result for an email that couldn't be verified."""
    return {
        "email": email,
        "status": "unknown",
        "confidence": "low",
        "is_reachable": "unknown",
        "is_disposable": False,
        "is_role_based": False,
        "is_catch_all": False,
        "is_free_provider": False,
        "syntax_valid": True,
        "mx_exists": False,
        "smtp_reachable": False,
        "mx_host": "",
        "smtp_response": "",
        "error_message": error_message,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
