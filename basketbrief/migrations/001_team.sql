-- Additive migration. Forward rollback: disable /team routes; preserve these tables.
CREATE TABLE IF NOT EXISTS team_schema(version INTEGER PRIMARY KEY, applied REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, email_notifications INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_sessions(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES team_users(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_limits(key TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS team_limits_key ON team_limits(key,created);
CREATE TABLE IF NOT EXISTS team_tokens(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES team_users(id), purpose TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, base_currency TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_members(project TEXT NOT NULL REFERENCES team_projects(id), user_id TEXT NOT NULL REFERENCES team_users(id),
 role TEXT NOT NULL CHECK(role IN ('coordinator','finance','contributor','donor')), PRIMARY KEY(project,user_id));
CREATE TABLE IF NOT EXISTS team_invites(hash TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES team_projects(id), role TEXT NOT NULL,
 creator TEXT NOT NULL REFERENCES team_users(id), expires REAL NOT NULL, used REAL);
CREATE TABLE IF NOT EXISTS team_expenses(id INTEGER PRIMARY KEY, project TEXT NOT NULL REFERENCES team_projects(id),
 owner TEXT NOT NULL REFERENCES team_users(id), description TEXT NOT NULL, amount TEXT, currency TEXT,
 status TEXT NOT NULL DEFAULT 'pending', supported INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
 attachment TEXT, fingerprint TEXT, reading TEXT, origin TEXT NOT NULL DEFAULT 'manual',
 reviewer TEXT REFERENCES team_users(id), fx_rate TEXT, fx_date TEXT, fx_source TEXT, created REAL NOT NULL, updated REAL NOT NULL,
 UNIQUE(project,fingerprint));
CREATE TABLE IF NOT EXISTS team_distribution(project TEXT PRIMARY KEY REFERENCES team_projects(id),
 loaded INTEGER, delivered INTEGER, returned INTEGER, households INTEGER, note TEXT NOT NULL, author TEXT NOT NULL REFERENCES team_users(id));
CREATE TABLE IF NOT EXISTS team_notifications(id INTEGER PRIMARY KEY, project TEXT REFERENCES team_projects(id),
 user_id TEXT NOT NULL REFERENCES team_users(id), kind TEXT NOT NULL, title TEXT NOT NULL, expense_id INTEGER,
 created REAL NOT NULL, read_at REAL);
CREATE INDEX IF NOT EXISTS team_notification_recipient ON team_notifications(user_id,id);
CREATE TABLE IF NOT EXISTS team_activity(id INTEGER PRIMARY KEY, project TEXT NOT NULL REFERENCES team_projects(id),
 actor TEXT REFERENCES team_users(id), action TEXT NOT NULL, detail TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_reports(id INTEGER PRIMARY KEY, project TEXT NOT NULL REFERENCES team_projects(id),
 version INTEGER NOT NULL, revision INTEGER NOT NULL, hash TEXT NOT NULL, payload TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft', approved_by TEXT REFERENCES team_users(id), created REAL NOT NULL, UNIQUE(project,version));
CREATE TABLE IF NOT EXISTS team_deliveries(report_id INTEGER NOT NULL REFERENCES team_reports(id), user_id TEXT NOT NULL REFERENCES team_users(id),
 created REAL NOT NULL, PRIMARY KEY(report_id,user_id));
CREATE TABLE IF NOT EXISTS team_mail_outbox(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES team_users(id),
 notification_id INTEGER UNIQUE REFERENCES team_notifications(id), subject TEXT NOT NULL, body TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS team_oauth_states(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES team_users(id), provider TEXT NOT NULL,
 verifier TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS team_mailboxes(user_id TEXT NOT NULL REFERENCES team_users(id), provider TEXT NOT NULL,
 address TEXT NOT NULL, credential TEXT NOT NULL, connected REAL NOT NULL, PRIMARY KEY(user_id,provider));
CREATE TABLE IF NOT EXISTS team_jobs(id INTEGER PRIMARY KEY, project TEXT NOT NULL REFERENCES team_projects(id),
 status TEXT NOT NULL DEFAULT 'queued', created REAL NOT NULL, started REAL, error TEXT);
