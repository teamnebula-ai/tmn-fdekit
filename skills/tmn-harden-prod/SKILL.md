---
name: tmn-harden-prod
description: (tmn) Security and failure-mode pass on a change or a service - map trust boundaries, check every path to each sensitive action, tenant isolation, secrets, injection, dependency risk, and what happens when things fail - and prove each issue with a repro. Use before shipping anything that touches auth, data access, payments, external input, file or network access, or customer data, when asked for a security review or threat model, or when asked "is this safe?".
---

# Harden

Assume a motivated user, a broken dependency and a careless future teammate.
The question for each risk is: can I show it happening? A list of theoretical
issues gets ignored. Two proven ones get fixed.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-harden-prod` override anything else in this skill.

## 1. Map the surface

Write a short list before reading code line by line:

- **Entry points**: routes, webhooks, queue consumers, scheduled jobs, CLI
  commands, agent tools, file uploads.
- **Identities**: who can call each one, and where the code learns who they
  are (session, token, API key, signed webhook).
- **Sensitive actions**: reads of other people's data, writes, deletes,
  sending (email, messages, payments), deploying, spending.
- **Trust boundaries**: every place data crosses from someone you don't
  control into code that acts on it.

## 2. Authorization: every path, every owner

- Each sensitive action checks the caller against the record's owner (tenant,
  org, user), using server-side identity. Never trust an owner id, role or
  name sent by the client.
- Find every path to the same action, not just the one being changed: bulk
  endpoints, upserts, imports, admin screens, background jobs, agent tool
  calls, GraphQL resolvers. `rg` for the model or table name and check each hit.
- Exemptions key on identity (an app or bot id), never on a name anyone can
  choose (a branch name, an email prefix, a display name).
- Data stores enforce it too where they can (row-level security, scoped
  credentials), so one missed check isn't a breach.
- **Prove it:** a test or curl where tenant B reads, updates and deletes
  tenant A's record. Each one must fail.

## 3. Input and injection

For every value that crosses a trust boundary, check:

- SQL and NoSQL injection (parameterised queries only), command injection
  (no shell strings built from input), template injection.
- Path traversal on any file path built from input; SSRF on any URL fetched
  from input (block internal ranges and metadata endpoints).
- XSS: output encoding by default, no raw HTML from users, a content
  security policy on web apps.
- Size and rate limits on uploads, list endpoints and anything that costs
  money per call. Regexes on user input that can backtrack forever.
- For LLM features: prompt injection from retrieved content, tool calls that
  act with more authority than the user has, and model output rendered or
  executed without checks.

## 4. Secrets and dependencies

- No secrets in code, fixtures, logs, error messages or client bundles.
  `scripts/pr_check.py` catches the common shapes; run gitleaks when it's
  available.
- Least privilege on every new token, role and service account. A read-only
  job gets a read-only credential.
- Dependencies: run the ecosystem's audit (`npm audit --omit=dev`,
  `pip-audit`, `govulncheck ./...`, `cargo audit`) and check new packages for
  maintenance, licence and typo-squatting. Pin versions.
- Webhooks verify signatures. Sessions and cookies are `Secure`, `HttpOnly`
  and `SameSite` set deliberately for the flow.

## 5. Failure modes

- Every external call has a timeout, a bounded retry with backoff, and a
  defined failure behaviour. For anything that sends, allows or deletes, that
  behaviour is fail closed.
- An error never becomes "no data" or "approved". A missing required setting
  stops startup with a clear message. No hardcoded fallback person, key, org
  or URL.
- Retries and duplicate deliveries are safe (idempotency keys, unique
  constraints).
- Logs say what failed and for which record, without secrets or personal data.
  Alerts fire on the failure a user would notice.
- Risky features (sending, spending, deleting) are off by default and behind
  a flag someone has to turn on.

## 6. Report

Same calibration as the `tmn-pr-review` skill. Every issue has a location, a repro or
quoted line, severity, and a concrete fix. Put fixes for confirmed blockers in
the change (with the wrong-owner test) before shipping. Everything else
becomes a ticket with the repro attached. Say what you didn't cover.
