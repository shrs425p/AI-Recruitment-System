import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_interview_email(
    smtp_host,
    smtp_port,
    smtp_email,
    smtp_password,
    recipient_email,
    candidate_name,
    job_title,
    interview_slot,
    hr_name="",
    company="",
):
    """
    Send an interview invitation email to a candidate.

    Returns (True, "") on success or (False, error_string) on failure.
    """
    if not recipient_email:
        return False, "No recipient email address."
    if not smtp_email or not smtp_password:
        return False, "SMTP credentials not configured in Settings."

    # Format the interview date nicely
    try:
        dt = datetime.strptime(interview_slot, "%Y-%m-%d %H:%M")
        date_display = dt.strftime("%A, %B %d %Y at %I:%M %p")
    except (ValueError, TypeError):
        date_display = interview_slot or "TBD"

    company_line = f" at {company}" if company else ""
    hr_line = hr_name or "The Hiring Team"

    subject = f"Interview Invitation — {job_title}"

    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
        <h2 style="color:#18181b;">Interview Invitation</h2>
        <p>Dear <strong>{candidate_name}</strong>,</p>
        <p>We are pleased to inform you that you have been shortlisted for the position of
           <strong>{job_title}</strong>{company_line}.</p>
        <p>Your interview has been scheduled for:</p>
        <div style="background:#f4f4f5;padding:16px 20px;border-radius:8px;margin:16px 0;font-size:15px;">
            <strong>{date_display}</strong>
        </div>
        <p>Please ensure you are available at the above time. If you need to reschedule,
           reply to this email at your earliest convenience.</p>
        <p style="margin-top:24px;">Best regards,<br><strong>{hr_line}</strong>{company_line}</p>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin-top:32px;">
        <p style="font-size:12px;color:#a1a1aa;">
            This is an automated message from the AI Recruitment System.
        </p>
    </div>
    """

    body_text = (
        f"Dear {candidate_name},\n\n"
        f"You have been shortlisted for the position of {job_title}{company_line}.\n\n"
        f"Interview scheduled: {date_display}\n\n"
        f"Please ensure availability. Reply to reschedule.\n\n"
        f"Best regards,\n{hr_line}{company_line}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_email
    msg["To"] = recipient_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def test_smtp_connection() -> tuple[bool, str]:
    """
    Test the connection and login to the SMTP server using values currently in config.py.
    Returns (True, "") on success, or (False, error_message) on failure.
    """
    import config as cfg
    smtp_host = getattr(cfg, "SMTP_HOST", "").strip()
    try:
        smtp_port = int(getattr(cfg, "SMTP_PORT", 587))
    except (TypeError, ValueError):
        smtp_port = 587
    smtp_email = getattr(cfg, "SMTP_EMAIL", "").strip()
    smtp_password = getattr(cfg, "SMTP_PASSWORD", "").strip()

    if not smtp_host:
        return False, "SMTP Host is not configured."
    if not smtp_email or not smtp_password:
        return False, "SMTP credentials are not configured."

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
        return True, ""
    except Exception as e:
        return False, str(e)
