# Team workspace implementation

The existing guided demonstration remains available at `/`. Real workspaces at `/team` use individual accounts and project memberships, not the demonstration's role-switching tokens.

Acceptance scope:

- Individual sign-in, expiring sessions, one-use invitations and coordinator-controlled membership revocation.
- Multiple expenses per project, original currency totals and reviewed exchange rates with date/source. Approved snapshots retain their original values.
- Contributors upload evidence; finance/coordinators review it. A contributor sees their own evidence, reviewers see all project evidence, donors see approved snapshots only.
- Persistent recipient-specific notifications, unread counts and refresh across independently signed-in browsers. A successful upload is not evidence that someone has read it.
- Optional email notifications via configured SMTP, verified addresses and user preferences. Configuration or SMTP failure must never be reported as delivery.
- Explicit PNG, JPEG and PDF attachment import from a selected `.eml` file or a connected personal mailbox. Importing a requested receipt can complete an existing expense without creating a second charge. Multi-page PDFs retain the original and require all-page human review; only page one is machine-read.
- Gmail app-password connections were tested with an owner-authorized private mailbox. Passwords/tokens are encrypted, and IMAP uses a read-only selection plus `BODY.PEEK`. Imports require a message and attachment selection; there is no automatic whole-inbox ingestion.
- Google OAuth and Outlook/Microsoft 365 delegated OAuth handlers are implemented with account-bound one-use state and PKCE. Public provider client registration and a live consent test are still required. An app-password test does not verify OAuth.
- Versioned additive SQLite migration, a backup before rollout, migration checks on a copy of the existing database, and cross-account/browser regression checks.

Do not describe an unconfigured external email or OAuth integration as active. Do not send test mail to real people without permission.

## Deployment configuration

The database migration adds `team_*` tables without rewriting the guided demonstration. Back up the SQLite database with its backup API before deployment. Back up the private `.team-token-key` beside the database too, or provide a stable Fernet key as `BASKETBRIEF_TOKEN_KEY`. Losing this key requires users to reconnect; it does not expose plaintext credentials. Keep both backups private.

Set `BASKETBRIEF_PUBLIC_URL` to the HTTPS origin. Google needs `BASKETBRIEF_GMAIL_CLIENT_ID` and `BASKETBRIEF_GMAIL_CLIENT_SECRET`, with redirect `/api/team/mail/gmail/callback`. Microsoft needs `BASKETBRIEF_OUTLOOK_CLIENT_ID` and `BASKETBRIEF_OUTLOOK_CLIENT_SECRET`, with redirect `/api/team/mail/outlook/callback`. Configure the appropriate consent audience and provider permissions before enabling either button. Gmail requests read-only Gmail access; Microsoft requests delegated Mail.Read, User.Read and offline access. These connections belong to the signed-in user, not the project.

Optional notification delivery requires `BASKETBRIEF_SMTP_HOST`, `BASKETBRIEF_SMTP_PORT`, `BASKETBRIEF_MAIL_FROM`, and, when required, `BASKETBRIEF_SMTP_USER`/`BASKETBRIEF_SMTP_PASSWORD`. Use an application sender, not a contributor's connected mailbox. Port 465 uses implicit TLS; other SMTP ports require STARTTLS. Users must verify their address and enable notifications. Outbox retries preserve a message ID; SMTP acceptance is not proof of reading and delivery may be duplicated after a process interruption.

Disconnect deletes the application's saved credential and pending OAuth states. Provider-side consent or a Google app password can also be revoked in the provider's account settings. Previously imported documents remain project evidence and are not deleted by disconnect.

To roll back application code, leave the additive tables and private uploads intact. Do not restore an old database over newer user evidence.
