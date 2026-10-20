import logging
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _sanitize_header(value: str) -> str:
    """
    Remove linebreaks and carriage returns from email header values to prevent
    header injection attacks or ValueError exceptions from email libraries.
    """
    if not value or not isinstance(value, str):
        return ""
    return re.sub(r"[\r\n]+", " ", value).strip()


def _connect_smtp(smtp_host: str, smtp_port: int, timeout: int = 30):
    """
    Establish an SMTP connection. If smtp_port is 465, use smtplib.SMTP_SSL directly
    for implicit SSL. For other ports, initialize smtplib.SMTP and upgrade via starttls().
    """
    try:
        port = int(smtp_port)
    except (TypeError, ValueError):
        port = 587

    if port == 465:
        return smtplib.SMTP_SSL(smtp_host, port, timeout=timeout)
    server = smtplib.SMTP(smtp_host, port, timeout=timeout)
    server.starttls()
    return server


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
    interview_url=None,
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

    import config as cfg
    custom_subject = getattr(cfg, "EMAIL_TEMPLATE_SUBJECT", "").strip()
    custom_body = getattr(cfg, "EMAIL_TEMPLATE_BODY", "").strip()

    template_vars = {
        "candidate_name": candidate_name,
        "job_title": job_title,
        "selected_slot": date_display,
        "interview_slot": date_display,
        "company": company or "Our Company",
        "hr_name": hr_line,
        "interview_link": interview_url or "Link will be provided",
    }

    if custom_subject:
        try:
            subject = custom_subject.format(**template_vars)
        except Exception:
            subject = f"Interview Invitation — {job_title}"
    else:
        subject = f"Interview Invitation — {job_title}"

    if custom_body:
        try:
            body_text = custom_body.format(**template_vars)
        except Exception:
            body_text = (
                f"Dear {candidate_name},\n\n"
                f"You have been shortlisted for the position of {job_title}{company_line}.\n\n"
                f"Interview scheduled: {date_display}\n\n"
                f"Best regards,\n{hr_line}{company_line}\n"
            )
    else:
        body_text = (
            f"Dear {candidate_name},\n\n"
            f"You have been shortlisted for the position of {job_title}{company_line}.\n\n"
            f"Interview scheduled: {date_display}\n\n"
            f"Best regards,\n{hr_line}{company_line}\n"
        )

    link_html = ""
    if interview_url:
        link_html = f"""
        <p style="margin-top:24px;">Please use the following unique link to access your AI Interview portal at the scheduled time:</p>
        <div style="margin:24px 0;">
            <a href="{interview_url}" style="background-color:#18181b;color:#ffffff;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:600;display:inline-block;">Open Interview Portal</a>
        </div>
        """

    if custom_body:
        formatted_custom = body_text.replace("\n", "<br>")
        content_html = f"<div style='line-height:1.6;'>{formatted_custom}</div>"
    else:
        content_html = f"""
        <p>Dear <strong>{candidate_name}</strong>,</p>
        <p>We are pleased to inform you that you have been shortlisted for the position of
           <strong>{job_title}</strong>{company_line}.</p>
        <p>Your interview has been scheduled for:</p>
        <div style="background:#f4f4f5;padding:16px 20px;border-radius:8px;margin:16px 0;font-size:15px;">
            <strong>{date_display}</strong>
        </div>
        """

    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;">
        <h2 style="color:#18181b;">Interview Invitation</h2>
        {content_html}
        {link_html}
        <p>Please ensure you are available at the above time. If you need to reschedule,
           reply to this email at your earliest convenience.</p>
        <p style="margin-top:24px;">Best regards,<br><strong>{hr_line}</strong>{company_line}</p>
        <hr style="border:none;border-top:1px solid #e4e4e7;margin-top:32px;">
        <p style="font-size:12px;color:#a1a1aa;">
            This is an automated message from the AI Recruitment System.
        </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _sanitize_header(subject)
    msg["From"] = _sanitize_header(smtp_email)
    msg["To"] = _sanitize_header(recipient_email)
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with _connect_smtp(smtp_host, smtp_port, timeout=30) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        logger.warning("Failed to send interview invitation email: %s", e)
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
        with _connect_smtp(smtp_host, smtp_port, timeout=10) as server:
            server.login(smtp_email, smtp_password)
        return True, ""
    except Exception as e:
        logger.warning("SMTP connection test failed: %s", e)
        return False, str(e)


def send_feedback_email(
    smtp_host: str,
    smtp_port: int,
    smtp_email: str,
    smtp_password: str,
    recipient_email: str,
    candidate_name: str,
    subject: str,
    feedback_text: str,
    company: str = "",
) -> tuple[bool, str]:
    """
    Send a tailored feedback or regret email to a candidate.
    Returns (True, "") on success or (False, error_string) on failure.
    """
    if not recipient_email:
        return False, "No recipient email address."
    if not smtp_email or not smtp_password:
        return False, "SMTP credentials not configured in Settings."

    company_title = company or "The Hiring Team"
    paragraphs = [p.strip() for p in feedback_text.split("\n\n") if p.strip()]
    paragraphs_html = "".join(f"<p style='color:#374151; font-size:15px; line-height:1.6;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)

    body_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:620px;margin:0 auto;padding:28px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;">
        <div style="border-bottom:1px solid #e5e7eb;padding-bottom:16px;margin-bottom:20px;">
            <h2 style="color:#111827;font-size:20px;font-weight:700;margin:0;">Candidate Evaluation Feedback</h2>
            <p style="color:#6b7280;font-size:13px;margin:4px 0 0 0;">Application Status & Review</p>
        </div>
        {paragraphs_html}
        <div style="margin-top:28px;padding-top:16px;border-top:1px solid #e5e7eb;">
            <p style="color:#111827;font-weight:600;margin:0;font-size:14px;">{company_title}</p>
            <p style="color:#9ca3af;font-size:12px;margin:4px 0 0 0;">This email contains confidential candidate feedback generated by the Talent Acquisition team.</p>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _sanitize_header(subject or "Your Application Feedback")
    msg["From"] = _sanitize_header(smtp_email)
    msg["To"] = _sanitize_header(recipient_email)
    msg.attach(MIMEText(feedback_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with _connect_smtp(smtp_host, smtp_port, timeout=25) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        logger.warning("Failed to send feedback email: %s", e)
        return False, str(e)


def send_selection_offer_email(
    smtp_host: str,
    smtp_port: int,
    smtp_email: str,
    smtp_password: str,
    recipient_email: str,
    candidate_name: str,
    subject: str,
    offer_letter: str,
    job_title: str = "",
    company: str = "",
) -> tuple[bool, str]:
    """
    Send a formal job offer / selection letter email to a successful candidate.
    Returns (True, "") on success or (False, error_string) on failure.
    """
    if not recipient_email:
        return False, "No recipient email address."
    if not smtp_email or not smtp_password:
        return False, "SMTP credentials not configured in Settings."

    company_title = company or "The Hiring Team"
    role_title = job_title or "Offered Position"
    paragraphs = [p.strip() for p in offer_letter.split("\n\n") if p.strip()]
    paragraphs_html = "".join(f"<p style='color:#374151; font-size:15px; line-height:1.6; margin-bottom:14px;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)

    body_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;padding:32px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background:linear-gradient(135deg, #059669 0%, #10b981 100%);padding:20px 24px;border-radius:8px;margin-bottom:24px;color:#ffffff;">
            <div style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:0.9;">Formal Offer of Employment</div>
            <h1 style="font-size:22px;font-weight:700;margin:6px 0 0 0;color:#ffffff;">Congratulations, {candidate_name}!</h1>
            <p style="font-size:14px;margin:4px 0 0 0;opacity:0.95;">Position: {role_title}</p>
        </div>
        <div style="padding:0 4px;">
            {paragraphs_html}
        </div>
        <div style="margin-top:32px;padding-top:20px;border-top:1px solid #e5e7eb;">
            <p style="color:#111827;font-weight:700;margin:0;font-size:14px;">{company_title}</p>
            <p style="color:#9ca3af;font-size:12px;margin:4px 0 0 0;">This email contains confidential offer details and onboarding instructions.</p>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _sanitize_header(subject or f"Job Offer: {role_title} - Welcome to {company_title}")
    msg["From"] = _sanitize_header(smtp_email)
    msg["To"] = _sanitize_header(recipient_email)
    msg.attach(MIMEText(offer_letter, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with _connect_smtp(smtp_host, smtp_port, timeout=25) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        logger.warning("Failed to send offer email: %s", e)
        return False, str(e)


