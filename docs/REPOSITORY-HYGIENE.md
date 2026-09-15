# Repository publication check

Checked on 2026-09-15, before the submission deadline.

- Gitleaks scanned all 47 commits present at the first check (about 1.12 MB of text) with redacted output and reported no detected secrets. This is a detector result, not a guarantee that every secret format is covered.
- A second history scan after the fixes and publication of synthetic live-probe results covered 50 commits (about 1.25 MB) and also reported no detected secrets.
- The 32 tracked `run/uploads` PNGs had only two distinct contents. Both were visually reviewed synthetic demo receipts, not private bank statements or mailbox attachments. They were removed from the current Git tree; local copies remain. Their synthetic contents remain in earlier commits.
- Runtime uploads, environment files, SQLite sidecar files, local assistant tooling, and the account-specific AWS deployment target are now ignored. The included deployment example uses a placeholder account ID. The former AWS account ID is an identifier, not an authentication credential, and remains in history.
- No tracked database, mailbox export, PDF attachment, private key, environment file, or credential file was found in the inspected current tree or historical path inventory.
- The public sample receipt is intentionally fictional and remains available for reproduction. Public film assets and screenshots use the fictional demonstration or synthetic staging accounts.

The four bundled font families now include their upstream OFL copyright/license notices alongside the assets, linked from `THIRD-PARTY-NOTICES.md`.

Private document reviews and raw scanner output stay outside the repository. This check does not cover every external service log, GitHub cache or account setting, and is not an independent security audit.
