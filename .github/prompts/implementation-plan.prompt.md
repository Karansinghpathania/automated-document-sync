# Implementation Planning — Automated Documentation Sync

Act as the Implementation Planner defined in:

```text
.github/agents/implementation-planner.agent.md
```

Read the following documents before doing anything:

```text
docs/user-story.md
docs/requirements.md
docs/architecture.md
docs/design-review.md
README.md
```

Treat them as the authoritative project context.

---

## Task

Create:

```text
docs/impl-plan.md
```

Convert the approved architecture into a concrete, dependency-ordered implementation plan for Phase 6.

Do not implement the code yet.

---

## Critical Planning Requirements

The implementation plan must explicitly cover these architectural components:

1. Orchestrator
2. Change Detector
3. Impact Analyzer
4. Redaction Service
5. Doc Generator
6. Validators
7. Deduplication / Idempotency
8. Committer
9. Artifact Manager
10. Native GitHub approval integration
11. Lightweight Logging

---

## Dependency Ordering

Determine the correct implementation order.

The plan should generally move from:

```text
foundations
→ domain contracts
→ change detection
→ impact analysis
→ validation
→ security/redaction
→ AI integration
→ idempotency
→ commit safety
→ GitHub workflow orchestration
→ end-to-end integration
```

Do not blindly follow this order if the architecture or technical dependencies justify a better sequence. Explain any significant deviation.

---

## Required Design-Review Resolutions

The plan MUST explicitly implement the accepted design-review findings.

### DR-001 — Stale PR head

Implement:

```text
capture head SHA
        ↓
process exact state
        ↓
re-fetch head SHA
        ↓
if changed → abort
        ↓
otherwise commit
```

### DR-002 — Human approval

Use native:

```text
GitHub Reviews
+
CODEOWNERS
+
Branch Protection
+
Automated Documentation Check
```

Do not create a custom approval-monitor service.

### DR-003 — Prompt injection / file scope

Repository content is untrusted.

Generated changes must be restricted to approved documentation paths.

### DR-004 — Validation

Implement deterministic structural validation where technically determinable.

Do not claim automation proves semantic correctness when it cannot.

Human CODEOWNER review remains part of the correctness boundary.

### DR-005 — Secret redaction

The outbound AI corpus must be scanned completely.

Redaction is fail-closed.

If safe sanitization cannot be established:

```text
no AI call
no secret logging
no secret artifact
fail with sanitized diagnostic
```

### DR-006 — Runtime

Respect the 10-minute overall runtime limit.

Define implementation-level phase budgets without inventing architecture-level requirements.

### DR-007 — Idempotency

Use a deterministic processing identity based on the relevant PR state and exact head SHA.

Prevent:

* duplicate AI calls
* duplicate documentation commits
* stale commits
* race-induced updates

### DR-008 — Diagnostics

Implement the required diagnostic information from FR-010/NFR-006.

Do not over-engineer the artifact system into a separate service.

---

## Requirement Traceability

Every requirement from `docs/requirements.md` must map to implementation tasks.

Check the actual requirement IDs before referencing them.

Do NOT invent identifiers such as:

```text
FR-016
```

The current requirements use the approved FR/NFR identifiers only.

If a requirement cannot be mapped cleanly, identify the problem instead of silently inventing a task or requirement.

---

## Technology Selection

The architecture intentionally uses capability-first technology decisions.

During planning:

* select concrete libraries/tools only where necessary;
* justify each important choice;
* prefer mature, lightweight Python-compatible tooling;
* prefer deterministic CLI/library behavior;
* avoid unnecessary dependencies;
* keep GitHub Action startup/runtime overhead low.

Do not introduce databases, queues, persistent services, or microservices.

---

## Testing

Every implementation task must include tests.

The plan must include:

* unit tests;
* integration tests;
* failure-path tests;
* security tests;
* concurrency/idempotency tests;
* GitHub workflow tests;
* end-to-end verification.

Relevant tests should be selected based on changed files where determinable, consistent with FR-014.

---

## Failure Handling

Create a complete failure matrix covering:

* malformed OpenAPI;
* Markdown failure;
* broken links;
* structural mismatch;
* relevant test failure;
* AI timeout;
* AI HTTP 5xx;
* AI authentication failure;
* secret cannot be sanitized;
* prompt injection/path violation;
* stale PR head;
* duplicate processing;
* concurrent workflow runs;
* GitHub API/commit failure;
* artifact upload failure;
* overall timeout;
* missing or invalid CODEOWNERS.

For each failure state:

```text
detect
→ classify
→ retry or do not retry
→ commit allowed?
→ check result
→ diagnostic artifact
```

---

## Final Quality Gate

Before writing `docs/impl-plan.md`, verify:

* every architecture component has implementation coverage;
* every requirement maps to a task;
* every accepted design-review finding maps to a task;
* task dependencies are coherent;
* no task requires an unimplemented prerequisite;
* security boundaries are preserved;
* stale-run protection is explicit;
* idempotency is explicit;
* human approval is not replaced by automation;
* AI is not treated as authoritative;
* no FR-016 references exist;
* no unnecessary infrastructure was introduced;
* implementation tasks are small enough for Agent Mode to execute safely.

Then create only:

```text
docs/impl-plan.md
```

Do not modify source code or any previous SDLC artifact.
