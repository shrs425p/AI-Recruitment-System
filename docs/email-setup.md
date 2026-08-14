# Email Setup

This document covers how to configure email for scheduling notifications, what templates are available, and how to set up the most common email providers.

---

## Overview

The email system uses Python's `smtplib` with STARTTLS encryption. It sends interview invitation emails to candidates during the scheduling stage.

Email is **optional** — the system works without it. If email is not configured, you can still manually copy the interview URL and share it with candidates.

---

## Configuration

Set these values in Settings → Email:

| Setting | Description |
|---|---|
| **SMTP Host** | Your email provider's outgoing mail server |
| **SMTP Port** | Usually `587` (STARTTLS) or `465` (SSL) |
| **Sender Email** | The email address emails are sent from |
| **Password** | Email account password or app password |
| **Display Name** | HR manager name shown in the email body |
| **Company** | Company name shown in the email body |

---

## Provider Setup

### Gmail

Gmail requires an **App Password** (not your regular account password) if 2-Step Verification is enabled, which it usually is.

**Step 1 — Enable 2-Step Verification** (if not already on):
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "How you sign in to Google" → click **2-Step Verification** → Enable it

**Step 2 — Create an App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in if prompted
3. Under "Select app" → choose **Mail** (or type a custom name)
4. Under "Select device" → choose **Windows Computer**
5. Click **Generate** → copy the 16-character app password (no spaces)

**Settings:**
```
SMTP Host:  smtp.gmail.com
SMTP Port:  587
Email:      yourname@gmail.com
Password:   <16-char app password>
```

---

### Outlook / Hotmail / Live

```
SMTP Host:  smtp-mail.outlook.com
SMTP Port:  587
Email:      yourname@outlook.com
Password:   <your Outlook password>
```

If your organisation uses Microsoft 365 with modern authentication, you may need to enable SMTP AUTH in the Microsoft 365 admin centre:
1. Admin → Users → Active users → select your user
2. Mail → Manage email apps → enable **Authenticated SMTP**

---

### Yahoo Mail

Yahoo requires an app password similar to Gmail:
1. Go to [security.yahoo.com](https://security.yahoo.com)
2. Sign in → App passwords → Generate
3. Use the generated password

```
SMTP Host:  smtp.mail.yahoo.com
SMTP Port:  587
Email:      yourname@yahoo.com
Password:   <app password>
```

---

### Custom SMTP (Office 365, cPanel, etc.)

Use whatever SMTP settings your email provider gives you. The system uses STARTTLS on port 587 by default. If your server requires direct SSL (port 465), change `SMTP_PORT` to `465` — but note the code uses `starttls()` so port 465 SSL would need a code change to use `smtplib.SMTP_SSL`.

---

## Testing the Connection

From the Settings page → Email → click **Test Connection**. This sends a test login to the SMTP server without actually sending an email.

Or from the command line:
```bash
python -c "from src.email_sender import test_smtp_connection; print(test_smtp_connection())"
```

Returns `(True, '')` on success or `(False, '<error message>')` on failure.

---

## Email Templates

The system has a built-in default email. You can override both the subject and body with your own template in Settings → Email.

### Default Email

**Subject:** `Interview Invitation — {job_title}`

**Body (HTML):**
```
Dear {candidate_name},

We are pleased to inform you that you have been shortlisted for the position of
{job_title} at {company}.

Your interview has been scheduled for:
  {selected_slot}

Please ensure you are available at the above time. If you need to reschedule,
reply to this email at your earliest convenience.

Best regards,
{hr_name}
```

### Custom Template Variables

When writing a custom subject or body, these variables are available:

| Variable | Value |
|---|---|
| `{candidate_name}` | Candidate's full name |
| `{job_title}` | The job title from the scheduling run |
| `{selected_slot}` | Interview date and time (e.g. `Wednesday, August 20 2026 at 10:00 AM`) |
| `{interview_slot}` | Same as `{selected_slot}` (alias) |
| `{company}` | Your company name from Settings → General |
| `{hr_name}` | HR display name from Settings → General |
| `{interview_link}` | Currently a placeholder — the candidate portal URL is included separately |

**Example custom subject:**
```
Your interview for {job_title} is confirmed — {selected_slot}
```

**Example custom body:**
```
Hi {candidate_name},

Congratulations! You've been selected for an interview at {company} for the {job_title} role.

Your slot: {selected_slot}

We'll send you a separate link to access the online interview portal.

Looking forward to speaking with you.

— {hr_name}
```

If a variable is missing or the template has a syntax error, the system falls back to the default email automatically.

---

## What the Email Looks Like

The email is sent as **multipart** (both plain text and HTML versions). Email clients that support HTML show a styled version with a boxed interview time. Plain text fallback is included for older clients.

The sender address will be the `SMTP_EMAIL` you configured. To change the display name (the name shown in recipients' inboxes), most SMTP servers respect the `From: "HR Admin <hr@company.com>"` format — but this is not currently configurable from the UI; the From header is set to the SMTP email only.

---

## Troubleshooting Email

### `(535, 'Authentication failed')`
→ Wrong email or password. For Gmail, make sure you're using the App Password, not your account password.

### `Connection refused` or `timed out`
→ Wrong SMTP host or port. Double-check with your provider's documentation.

### `(534, 'Please log in via your web browser')`
→ Gmail is blocking the login. This usually means 2-Step Verification is off or you're not using an App Password.

### Emails going to spam
→ Common with SMTP relay through Gmail/Yahoo for non-personal domains. Consider using a service like SendGrid or Mailgun if emails are consistently marked as spam.

### `No recipient email address`
→ The candidate's email was not found in their NLP profile. Check the `*_nlp.json` file — if `personal_info.email` is empty, the email was not in the resume. You'll need to add it manually in the schedule file.
