---
tags: [review]
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Agent]
---

Can you review the change on branch feat/ORD-7-cancel against main in ./repo before we merge it? Ticket ORD-7, "Customers can cancel an order". Acceptance criteria: (1) the owner can cancel their own open order and its status becomes cancelled; (2) a customer can never cancel another tenant's order, which returns 404 and leaves the order untouched; (3) cancelling an order that does not exist returns 404; (4) cancelling the same order twice is safe. There's no GitHub remote, so don't try to post anything: write the review comment you would post to review.md and tell me your verdict.

Input files: repo.bundle
