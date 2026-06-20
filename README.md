# Email Verifier Pro | $0.85/1k — Bulk Email Validation & List Cleaning

Verify email addresses at scale with **real SMTP checks** — not just syntax validation. Email Verifier Pro connects directly to mail servers to confirm whether a mailbox actually exists, giving you the most accurate results possible.

**Stop wasting money on bounced emails.** Whether you're doing cold outreach, cleaning your CRM, or validating lead lists, this actor tells you exactly which emails are safe to send to and which ones will bounce.

## Why Email Verifier Pro?

| Feature | Email Verifier Pro | Other Actors |
|:---|:---:|:---:|
| **Price per 1,000 emails** | **$0.85** | $1.00 – $9.00 |
| Real SMTP verification | ✅ | Some ❌ |
| Disposable email detection | ✅ | Some ❌ |
| Catch-all domain detection | ✅ | Some ❌ |
| Role-based email detection | ✅ | Rare |
| Free provider detection | ✅ | Rare |
| CSV URL upload | ✅ | ❌ Most are JSON-only |
| Live progress tracking | ✅ | ❌ |
| Smart retry on failures | ✅ | ❌ |
| No external API key needed | ✅ | ❌ Many require 3rd-party accounts |

## Use Cases

- **Cold email outreach** — Verify your prospect list before sending to protect your sender reputation and avoid getting flagged as spam
- **Marketing campaigns** — Clean your email list to reduce bounce rates and improve deliverability metrics
- **CRM maintenance** — Remove invalid, disposable, and role-based emails from your database on a regular schedule
- **Lead generation** — Validate scraped email lists to ensure you're only reaching out to real people
- **E-commerce** — Verify customer email addresses at checkout to reduce failed order confirmations
- **Data enrichment pipelines** — Chain with other Apify actors: scrape emails → verify → export clean list

## How It Works

Email Verifier Pro performs **7 checks** on every email address:

### Why Choose Email Verifier Pro?
- ⚡ **Lightning Fast:** Defaults to 10 simultaneous connections. Verify massive lists in minutes, not hours.
- 🎯 **Deep SMTP Validation:** We don't just check syntax. We talk directly to the target mail server.
- 💰 **Cheapest Full-SMTP Validation:** Just $0.85 per 1,000 emails. Others charge $2.00+ for the same accuracy.
- 🎁 **100 Email Free Trial:** Users on the free Apify plan can fetch up to 100 leads per run to test the accuracy before paying!
- 🛡️ **Role-Based & Disposable Detection:** Automatically flags `info@`, `admin@`, and temporary inboxes.
- 🔗 **Keeps Your Original Data:** Upload a CSV with names, companies, and custom IDs. We'll append the verification results without throwing away your original columns!
- 📈 **Live Progress Tracking:** See valid/invalid ratios in real-time as your list processes.)

1. **Syntax validation** — Is the email format correct? (`user@domain.com`)
2. **MX record lookup** — Does the domain have a mail server configured?
3. **SMTP handshake** — Can we connect to the mail server and confirm the mailbox exists?
4. **Disposable detection** — Is it a temporary/throwaway email? (Mailinator, Guerrilla Mail, etc.)
5. **Role-based detection** — Is it a generic address? (`info@`, `support@`, `admin@`)
6. **Catch-all detection** — Does the domain accept emails to any address? (makes verification unreliable)
7. **Free provider detection** — Is it Gmail, Yahoo, Outlook, or another free email service?

## Input

You can provide emails in **three ways** (use any one or combine them):

### Option 1: Paste emails directly
Use the **Email Addresses** field to paste a list of emails, one per line.

### Option 2: CSV file URL
Paste a URL to a CSV file in the **CSV File URL** field. We automatically detect the email column — or you can specify it manually. Supports:
- Direct download links
- Google Sheets (published as CSV)
- Dropbox shared links

### Option 3: Apify Dataset ID
If you've already scraped emails with another actor, paste the **Dataset ID** in the corresponding field. We'll read the emails directly — no need to export and re-upload.

### Advanced Settings

| Setting | Default | Description |
|:---|:---|:---|
| Concurrency | 10 | Emails verified simultaneously (1–30) |
| Max Retries | 2 | Retry count for temporary SMTP failures |
| Timeout | 30s | Max wait time per email |
| Max Emails | No limit | Cap the number of emails per run (up to 50,000) |

## Output

Each email produces a result row containing all of your original input columns (if you used a CSV or Dataset), plus our appended verification fields:

```json
{
    "email": "john@company.com",
    "status": "valid",
    "is_reachable": "safe",
    "is_disposable": false,
    "is_role_based": false,
    "is_catch_all": false,
    "is_free_provider": false,
    "syntax_valid": true,
    "mx_exists": true,
    "smtp_reachable": true,
    "mx_host": "alt1.aspmx.l.google.com",
    "smtp_response": "250 OK — Mailbox exists",
    "error_message": "",
    "verified_at": "2026-06-14T12:00:00Z"
}
```

### Business Status (`status`)

| Status | Meaning | Action |
|:---|:---|:---|
| `valid` | ✅ Mailbox exists and accepts email | Safe to send |
| `invalid` | ❌ Mailbox doesn't exist or domain has no mail server | Remove from list |
| `risky` | ⚠️ Mailbox exists but may be a catch-all, disposable, or role-based | Review manually |
| `unknown` | ❓ Could not determine — server timeout or temporary error | Retry later |

### Technical Details

We expose the raw technical signals so you can build your own custom logic:
- `is_reachable`: Raw Reacher API status (`safe`, `invalid`, `risky`, `unknown`)
- `smtp_reachable`: Boolean indicating if the SMTP server responded to our handshake
- `smtp_response`: The exact response message from the mail server (e.g., "550 User unknown")
- `mx_exists`: Boolean indicating if the domain has valid mail servers configured

Results are available as **JSON**, **CSV**, **Excel**, or **HTML** — download from the Dataset tab after the run completes.

## How to Reduce Email Bounce Rates

High bounce rates damage your sender reputation and can get your domain blacklisted. Here's how to use Email Verifier Pro to keep your lists clean:

1. **Before every campaign**: Run your list through Email Verifier Pro. Remove all `invalid` emails and review `risky` ones.
2. **Monthly CRM cleaning**: Schedule recurring runs to catch emails that have become invalid over time (employees leave, domains expire).
3. **At the point of collection**: Verify emails in real-time using the [Apify API](https://docs.apify.com/api/v2) to reject invalid addresses before they enter your database.

## Pricing

**$0.85 per 1,000 emails verified** — the most affordable full-SMTP verification on the Apify Store.

- No external API keys required
- No hidden fees or dual billing
- No monthly subscription — pay only for what you use
- You are charged per email verified (pay-per-event)

### Cost Examples

| List Size | Cost |
|:---|:---|
| 1,000 emails | $0.85 |
| 10,000 emails | $8.50 |
| 50,000 emails | $42.50 |
| 100,000 emails | $85.00 |

## Frequently Asked Questions

### How accurate is the verification?
We perform a **real SMTP handshake** with the recipient's mail server — the same process an actual email uses. This gives 95%+ accuracy for most providers. Catch-all domains are the exception: these accept all emails regardless, so we flag them as `risky` rather than giving a false `valid`.

### How fast is the verification?
With the default concurrency of 10, you can verify approximately **1,000 emails every 2 to 3 minutes** depending on how quickly the recipient mail servers respond. Gmail and Outlook are typically fast; smaller providers may be slower.

### Can I verify Gmail, Outlook, and Yahoo addresses?
Yes! We verify emails across all providers including Gmail, Outlook/Hotmail, Yahoo, custom domains, and more.

### What happens if my run is interrupted?
Results are pushed to the dataset **in real-time** — if your run stops partway through, all emails verified up to that point are saved. Simply run the remaining emails in a new run.

### Can I chain this with other Apify actors?
Absolutely! Scrape emails with any actor, then pass the Dataset ID directly to Email Verifier Pro. No export/import needed.

### Is there a rate limit?
Yes — we cap at **50,000 emails per run** to maintain verification quality. For larger lists, split into multiple runs.

## Integrations

Email Verifier Pro can be connected with almost any cloud service or web app thanks to integrations on the Apify platform. You can easily integrate with:
- **Make.com** & **Zapier** (Automate list cleaning when new leads arrive)
- **n8n** (Build self-hosted verification workflows)
- **Clay** & **Apollo** (Enrich and verify outbound prospects)
- **Google Sheets** (Verify rows automatically)

## API Usage & Code Examples

You can run this Actor programmatically using the [Apify API](https://docs.apify.com/api/v2) and official clients.

### JavaScript/Node.js

```javascript
import { ApifyClient } from 'apify-client';

const client = new ApifyClient({ token: 'YOUR_API_TOKEN' });

const run = await client.actor("YOUR_USERNAME/email-verifier-pro").call({
    emails: ["test@gmail.com", "contact@company.com"],
    concurrency: 10
});

const { items } = await client.dataset(run.defaultDatasetId).listItems();
console.log(items);
```

### Python

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_API_TOKEN")

run = client.actor("YOUR_USERNAME/email-verifier-pro").call(run_input={
    "emails": ["test@gmail.com", "contact@company.com"],
    "concurrency": 10
})

for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item)
```

### Apify CLI

```bash
echo '{
  "emails": [
    "test@gmail.com",
    "contact@company.com"
  ]
}' | apify call YOUR_USERNAME/email-verifier-pro --output-dataset
```

## Changelog

We actively maintain Email Verifier Pro to ensure maximum reliability and accuracy.

- **v1.1.0** — Added support for preserving all original input columns (like Names, Company, IDs) through the verification pipeline!
- **v1.0.6** — Improved automated daily health checks to guarantee 99.9% uptime.
- **v1.0.5** — Enhanced Apify dataset streaming for zero data loss during massive runs.

## Support & Reliability

This Actor is actively maintained. We strive for 100% reliability and are highly responsive to our users.

Found a bug, need a feature, or have a suggestion? Open an issue in our [GitHub Issues tab](https://github.com/zaleelbukhari/email-verifier-actor/issues) — we prioritize user feedback and respond within 24 hours.
