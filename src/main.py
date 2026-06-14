"""
Email Verifier Pro — Core Orchestrator

Reads input from any source (JSON list, CSV URL, or Apify dataset),
verifies emails in parallel via the Reacher API, pushes live results,
and tracks usage analytics.
"""

import asyncio
import time
from datetime import datetime, timezone

from apify import Actor

from .input_parser import parse_input, validate_email_format
from .verifier import verify_email, create_session, close_session
from .stats import increment_stats, get_stats


# ── Hard cap to protect VPS from overload ──
MAX_EMAILS_HARD_CAP = 50_000


async def main() -> None:
    """Main actor entry point."""
    async with Actor:
        Actor.log.info("🚀 Email Verifier Pro starting...")

        # ── 1. Read & validate input ──
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f"Input received: {list(actor_input.keys())}")

        concurrency = min(actor_input.get("concurrency", 5), 15)
        max_retries = min(actor_input.get("maxRetries", 2), 5)
        timeout = min(actor_input.get("timeout", 30), 120)
        max_emails = actor_input.get("maxEmails", 0)

        # ── 2. Extract emails from input source ──
        await Actor.set_status_message("📥 Parsing input...")

        try:
            raw_emails = await parse_input(actor_input)
        except ValueError as e:
            await Actor.fail(
                status_message=f"❌ Input error: {str(e)}"
            )
            return
        except Exception as e:
            Actor.log.exception(f"Failed to parse input: {e}")
            await Actor.fail(
                status_message=f"❌ Failed to parse input: {str(e)}"
            )
            return

        if not raw_emails:
            await Actor.fail(
                status_message=(
                    "❌ No emails found! Please provide emails via the "
                    "'Email Addresses' field, a CSV URL, or a Dataset ID."
                )
            )
            return

        # ── 3. Validate format & deduplicate ──
        seen = set()
        emails = []
        invalid_format_count = 0
        for email in raw_emails:
            email_lower = email.strip().lower()
            if not email_lower or email_lower in seen:
                continue
            seen.add(email_lower)
            if validate_email_format(email_lower):
                emails.append(email_lower)
            else:
                invalid_format_count += 1
                # Push invalid-format emails immediately
                await Actor.push_data({
                    "email": email.strip(),
                    "status": "invalid",
                    "is_reachable": "invalid",
                    "is_disposable": False,
                    "is_role_based": False,
                    "is_catch_all": False,
                    "is_free_provider": False,
                    "syntax_valid": False,
                    "mx_exists": False,
                    "smtp_reachable": False,
                    "mx_host": "",
                    "smtp_response": "Invalid email format",
                    "error_message": "Email address has invalid syntax",
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                })

        # Apply max emails cap
        effective_cap = MAX_EMAILS_HARD_CAP
        if max_emails > 0:
            effective_cap = min(max_emails, MAX_EMAILS_HARD_CAP)
        if len(emails) > effective_cap:
            Actor.log.warning(
                f"Email list truncated from {len(emails)} to {effective_cap} "
                f"(max per run: {effective_cap})"
            )
            emails = emails[:effective_cap]

        total = len(emails)
        total_with_invalid = total + invalid_format_count
        Actor.log.info(
            f"📋 {total} valid-format emails to verify "
            f"({invalid_format_count} invalid format, "
            f"{len(raw_emails) - total - invalid_format_count} duplicates removed)"
        )

        if total == 0:
            await Actor.set_status_message(
                f"✅ Done! All {invalid_format_count} emails had invalid format."
            )
            return

        # ── 4. Verify emails in parallel ──
        semaphore = asyncio.Semaphore(concurrency)
        session = await create_session(timeout)

        # Counters (thread-safe via asyncio single-thread)
        counters = {
            "completed": 0,
            "valid": 0,
            "invalid": 0,
            "risky": 0,
            "unknown": 0,
        }
        start_time = time.monotonic()

        # Check charging limits
        charging_manager = Actor.get_charging_manager()

        async def process_email(email: str) -> None:
            """Verify a single email with concurrency control."""
            # Check if user's budget is exhausted
            if charging_manager.is_at_max_event_count:
                return

            async with semaphore:
                result = await verify_email(
                    session=session,
                    email=email,
                    max_retries=max_retries,
                    timeout=timeout,
                )

                # Push result to dataset immediately (live results)
                await Actor.push_data(result)

                # Charge per verified email
                try:
                    await Actor.charge(event_name="email-verified", count=1)
                except Exception:
                    pass  # Don't fail on charge errors

                # Update counters
                status = result.get("status", "unknown")
                counters["completed"] += 1
                counters[status] = counters.get(status, 0) + 1

                # Update status message every 5 completions or at the end
                completed = counters["completed"]
                if completed % 5 == 0 or completed == total:
                    elapsed = time.monotonic() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = total - completed
                    eta_seconds = remaining / rate if rate > 0 else 0

                    # Format ETA
                    if eta_seconds < 60:
                        eta_str = f"{int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                    else:
                        eta_str = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"

                    pct = int(completed / total * 100)
                    status_msg = (
                        f"✅ {completed}/{total} ({pct}%) | "
                        f"🟢 {counters['valid']} valid | "
                        f"🔴 {counters['invalid']} invalid | "
                        f"🟡 {counters['risky']} risky | "
                        f"⏱️ ETA: {eta_str}"
                    )
                    await Actor.set_status_message(status_msg)

        # Launch all verification tasks
        await Actor.set_status_message(
            f"🔍 Verifying {total} emails (concurrency: {concurrency})..."
        )

        tasks = [process_email(email) for email in emails]
        await asyncio.gather(*tasks, return_exceptions=True)

        await close_session(session)

        # ── 5. Store summary in key-value store ──
        elapsed_total = time.monotonic() - start_time
        summary = {
            "total_input": len(raw_emails),
            "total_verified": counters["completed"],
            "invalid_format": invalid_format_count,
            "duplicates_removed": len(raw_emails) - total - invalid_format_count,
            "results": {
                "valid": counters["valid"],
                "invalid": counters["invalid"] + invalid_format_count,
                "risky": counters["risky"],
                "unknown": counters["unknown"],
            },
            "performance": {
                "elapsed_seconds": round(elapsed_total, 1),
                "emails_per_second": round(
                    counters["completed"] / elapsed_total, 2
                ) if elapsed_total > 0 else 0,
                "concurrency_used": concurrency,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        kvs = await Actor.open_key_value_store()
        await kvs.set_value("SUMMARY", summary)
        Actor.log.info(f"📊 Summary: {summary}")

        # ── 6. Update persistent usage analytics ──
        try:
            await increment_stats(
                emails_verified=counters["completed"] + invalid_format_count
            )
            stats = await get_stats()
            Actor.log.info(
                f"📈 Lifetime stats: {stats.get('total_emails_verified', 0)} "
                f"total emails verified across {stats.get('total_runs', 0)} runs"
            )
        except Exception as e:
            Actor.log.warning(f"Failed to update usage stats: {e}")

        # ── 7. Final status message ──
        total_all = counters["completed"] + invalid_format_count
        valid_pct = round(
            counters["valid"] / total_all * 100, 1
        ) if total_all > 0 else 0

        await Actor.set_status_message(
            f"🎉 Done! {total_all} emails verified — "
            f"🟢 {counters['valid']} valid ({valid_pct}%) | "
            f"🔴 {counters['invalid'] + invalid_format_count} invalid | "
            f"🟡 {counters['risky']} risky | "
            f"⏱️ {round(elapsed_total, 1)}s"
        )
        Actor.log.info("✅ Email Verifier Pro completed successfully!")
