# Security Policy

## Supported Versions

The `main` branch is the active development line.

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

If you find a vulnerability, contact the maintainer privately through GitHub or by using the contact method listed on the maintainer profile. Include:

- affected version or commit
- reproduction steps
- potential impact
- any suggested fix

## Sensitive Data

AI Vigil can store new-api keys in its database. API responses intentionally return only whether a key is configured, not the plaintext key.

For production deployments:

- change `ADMIN_PASSWORD`
- change `JWT_SECRET`
- restrict network access to the dashboard
- back up and protect the database
- avoid committing `.env` or database files
