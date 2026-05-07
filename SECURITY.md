# Security Policy

## Reporting a vulnerability

If you discover a security issue in OEDS, please do not open a public issue
with exploit details or exposed credentials.

Use one of these channels instead:

1. GitHub private vulnerability reporting, if it is enabled on the target repository
2. direct contact with the maintainers before public disclosure

## What to include

Please provide:

- a short description of the issue
- affected files, services, or endpoints
- reproduction steps or a proof of concept
- impact assessment if known
- whether secrets, tokens, or personal data may be affected

## Scope reminders

For this repository, common security-sensitive areas include:

- committed secrets or tokens
- crawler credentials in local environment files
- database credentials in deployment configurations
- exposed PostgREST or Grafana endpoints
- unsafe SQL or shell execution paths in crawler or script code

## Disclosure

Please allow maintainers reasonable time to verify and remediate the issue
before public disclosure.
