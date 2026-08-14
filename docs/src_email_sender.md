# Documentation for `email_sender.py`

**Path:** `src/email_sender.py`

## Module Docstring
No module-level docstring provided.

## Role
The `email_sender.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (send_interview_email, test_smtp_connection) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `smtplib`
- `datetime.datetime`
- `email.mime.multipart.MIMEMultipart`
- `email.mime.text.MIMEText`

### Global Variables
No global variables found.

### Classes
No classes found.

### Functions
#### `send_interview_email(smtp_host, smtp_port, smtp_email, smtp_password, recipient_email, candidate_name, job_title, interview_slot, hr_name, company)`
**Docstring:** Send an interview invitation email to a candidate.

Returns (True, "") on success or (False, error_string) on failure.

#### `test_smtp_connection()`
**Docstring:** Test the connection and login to the SMTP server using values currently in config.py.
Returns (True, "") on success, or (False, error_message) on failure.
