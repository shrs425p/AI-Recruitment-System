# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | Yes                |
| < 1.0   | No                 |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security vulnerabilities by emailing:
**pawarshreyas425@gmail.com**

Include the following in your report:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue
- Affected versions
- Any suggested fix (optional)

You will receive a response within **48 hours**. Once validated, we will:

1. Confirm receipt and severity within 48 hours
2. Work on a fix in a private branch
3. Release a patch and publish a security advisory
4. Credit you in the advisory (unless you prefer anonymity)

## Scope

This policy covers:

- The main application (`app/`, `src/`, `main.py`)
- Configuration handling (`config/`)
- API key storage and transmission
- Authentication and session management

## Out of Scope

- Issues in third-party libraries (please report to the upstream project)
- Issues requiring physical access to the machine
- Social engineering attacks
