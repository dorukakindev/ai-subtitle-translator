# Security Policy

## Supported version

Until stable releases are published, only the latest commit on the default
branch receives security fixes. Older commits are not guaranteed support.

## Reporting a vulnerability

Do not open a public issue for API-key exposure, arbitrary file access, private
subtitle or log disclosure, command execution, or provider-routing flaws.

Use the repository's **Security → Report a vulnerability** action to submit a
private security advisory. If private reporting is unavailable, do not place
sensitive details or real credentials in an issue; contact the repository owner
through GitHub and request a private channel.

A useful report contains:

- affected commit/version and operating system;
- safe, preferably synthetic reproduction steps;
- expected and actual behavior;
- likely impact;
- a short mitigation suggestion, if known.

Never send a real API key, private subtitle, personal path, or raw personal log.
Minimize the proof with synthetic values.

## Credential incidents

If a real key enters a repository, issue, or log, revoke and rotate it in the
provider dashboard immediately; do not wait for history cleanup. Then review
GitHub secret-scanning alerts and the affected history separately.

## Security boundaries

- Windows Credential Manager/keyring is the preferred credential store.
- The local fallback is obfuscation, not cryptographic encryption.
- A custom OpenAI-compatible base URL controls where subtitle text and the key
  are sent; use only endpoints you trust.
- The project does not guarantee model-output accuracy or uninterrupted service
  from third-party providers.
