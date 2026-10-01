# Phase 4 — Design Review Execution

Perform the Phase 4 design review of the Automated Documentation Sync architecture.

## Step 1 — Read the Source Documents

Before reviewing anything, read:

1. `docs/user-story.md`
2. `docs/requirements.md`
3. `docs/architecture.md`
4. `README.md`

Treat `docs/requirements.md` as the authoritative source of approved requirements.

Do not invent requirements or silently modify them.

---

## Step 2 — Review the Architecture

Apply all review rules defined in your agent instructions.

Critically examine the architecture rather than assuming it is correct.

In particular, try to find weaknesses in:

* requirements coverage
* component responsibilities
* end-to-end data flow
* AI safety
* secret handling
* GitHub Actions security
* permissions
* validation
* idempotency
* concurrency
* duplicate commits
* stale workflow runs
* workflow loops
* human approval
* CODEOWNERS
* branch protection
* failure handling
* timeout behavior
* observability
* traceability
* architectural complexity

Focus on concrete failure scenarios.

---

## Step 3 — Verify the End-to-End Flow

Trace this exact lifecycle:

```text
PR event
    ↓
Change Detection
    ↓
Impact Analysis
    ↓
Pre-generation validation
    ↓
Redaction
    ↓
AI generation
    ↓
Post-generation validation
    ↓
Deduplication / Idempotency
    ↓
Commit
    ↓
Automated Documentation Check
    ↓
CODEOWNER Review
    ↓
Branch Protection
    ↓
Merge
```

For every major transition determine:

* input
* output
* trust boundary
* failure behavior
* retry behavior
* concurrency implications
* whether stale state is possible

---

## Step 4 — Perform Adversarial Testing

Explicitly evaluate the adversarial scenarios defined by the Design Review Agent.

Do not only describe the happy path.

Pay particular attention to:

### Concurrent runs

What happens if two workflow runs process the same PR state simultaneously?

### PR changes during execution

What happens if a new commit is pushed while AI generation or validation is running?

### Generated documentation commit

What happens when the bot's documentation commit triggers another `pull_request` workflow?

### AI failure

What happens for:

* timeout
* HTTP 500
* authentication failure
* malformed response
* invalid generated documentation

### Secret exposure

What happens if changed source code contains a secret?

What happens if the secret cannot be safely redacted?

### Human approval

What happens if:

* CODEOWNERS is missing?
* an unauthorized user approves?
* a CODEOWNER approves and then a new commit is pushed?
* automated validation fails after approval?

### Validation

What happens if:

* OpenAPI is malformed?
* Markdown is invalid?
* links are broken?
* structural consistency fails?
* relevant tests fail?
* relevant tests cannot be determined?

### Runtime

What happens when the workflow approaches the 10-minute limit?

---

## Step 5 — Check Requirement Traceability

Verify every FR/NFR reference used by `docs/architecture.md`.

Ensure:

* referenced IDs actually exist
* no nonexistent requirement such as `FR-016` is referenced
* architectural decisions can be traced back to approved requirements
* no requirement is silently changed

Identify any mismatch as a review finding.

---

## Step 6 — Create the Review Artifact

Create:

```text
docs/design-review.md
```

Use exactly this structure:

```markdown
# Design Review — Automated Documentation Sync

## 1. Review Summary

## 2. Architecture Under Review

## 3. Requirements Coverage

## 4. Critical Findings

## 5. High-Severity Findings

## 6. Medium-Severity Findings

## 7. Low-Severity Findings

## 8. Adversarial Scenario Results

## 9. Security Review

## 10. Reliability and Concurrency Review

## 11. Validation Review

## 12. Human Approval Review

## 13. Runtime and Scalability Review

## 14. Observability Review

## 15. Traceability Review

## 16. Recommended Architecture Changes

## 17. Review Decision
```

---

## Finding Requirements

Every significant finding must include:

```markdown
### DR-XXX — <Finding Title>

**Severity:** CRITICAL | HIGH | MEDIUM | LOW

**Area:** <area>

**Problem:**
<What is wrong>

**Why it matters:**
<Concrete consequence or failure scenario>

**Evidence:**
<Architecture section and/or requirement>

**Recommended change:**
<Specific targeted architectural change>

**Requirement impact:**
<FR/NFR affected, if applicable>
```

Do not create vague findings such as:

> "Concurrency could be improved."

Instead describe the exact race condition and its consequence.

---

## Important Review Rules

### Do not modify the architecture yet

Do NOT modify:

```text
docs/architecture.md
```

even if you discover problems.

The purpose of this phase is to **identify and document problems first**.

We will decide which findings to accept later.

### Do not implement fixes

Do not modify:

* `src/`
* `tests/`
* `.github/workflows/`
* implementation files
* CI configuration

### Do not create implementation tasks

Implementation planning happens in the next phase.

### Do not invent requirements

Use only the approved requirements in:

```text
docs/requirements.md
```

### Do not add unnecessary architecture

Do not introduce:

* databases
* queues
* microservices
* persistent workers
* approval-monitor services
* metrics databases
* unnecessary external services

unless an existing approved requirement clearly requires them.

### Do not use numeric scores

Do not assign:

* architecture scores
* component scores
* percentages
* rankings

Use qualitative severity only.

---

## Review Decision

At the end of `docs/design-review.md`, choose exactly one:

```text
BLOCKED — architecture changes required
```

or

```text
CONDITIONALLY APPROVED — specific changes required
```

or

```text
APPROVED — ready for implementation planning
```

Base the decision on the actual findings.

Do not automatically change `docs/architecture.md` based on your findings.

Create only:

```text
docs/design-review.md
```
