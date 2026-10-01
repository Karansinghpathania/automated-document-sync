# Design Review — Automated Documentation Sync

## 1. Review Summary

The architecture is directionally consistent with the stated requirements and is intentionally minimal, which is a strength. It clearly separates change detection, impact analysis, redaction, generation, validation, commit, artifact handling, and approval gating, and it avoids unnecessary infrastructure. The core GitHub Action model and the requirement to use native CODEOWNERS review flow are sensible.

The design is not yet robust enough to proceed without changes. The main risks are in concurrency and idempotency, approval enforcement, and AI safety boundaries. In particular, the architecture under-specifies how stale workflow runs are rejected, how a missing or invalid CODEOWNERS policy is treated, and how untrusted repository content is prevented from causing prompt injection or unauthorized file mutation.

This review therefore concludes:

CONDITIONALLY APPROVED — specific changes required

---

## 2. Architecture Under Review

This review assessed the architecture defined in `docs/architecture.md` against the approved requirements in `docs/requirements.md` and the user story in `docs/user-story.md`.

The proposed system is a single GitHub Action pipeline that:

- triggers on pull_request events and workflow_dispatch,
- detects changed files and impacted docs,
- redacts obvious secrets before AI calls,
- generates documentation with OpenAI when needed,
- validates generated content with deterministic checks,
- commits a single atomic docs commit when validation passes,
- uploads private diagnostics,
- requires CODEOWNERS approval through native GitHub review flow.

This is a reasonable baseline architecture for a v1 implementation, but several critical assumptions remain incomplete or unverified.

---

## 3. Requirements Coverage

### Overall assessment

The architecture covers the expected v1 flow well in the happy path, but several requirements are only partially satisfied or are left to repository configuration and external behavior without explicit enforcement in the workflow itself.

### Mostly satisfied

- FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-011, FR-012, FR-014, and FR-015 are all represented in the architecture at a high level.
- The separation into orchestrator, detector, impact analyzer, redaction, generation, validators, deduplication, committer, and artifact manager matches the modular structure required by NFR-004.
- The architecture includes a clear GitHub Action flow and a defined AI boundary, which aligns with the intended v1 constraints.

### Partially satisfied or ambiguous

- FR-007 and FR-016 are only partially implemented at the architectural level. The design defines pre/post validation and says the check fails on validation errors, but it does not specify an enforceable, branch-head-aware commit gate that absolutely prevents stale runs from writing documentation after a new PR commit arrives.
- FR-008 is not fully satisfied architecturally. The architecture relies on repository branch protection and CODEOWNERS configuration, but the workflow itself does not define what happens when CODEOWNERS is absent, when the approving user is unauthorized, or when approval is given before the final doc change set exists.
- FR-009 is partially satisfied because failure reporting is described, but the architecture does not define a deterministic per-failure output contract for all error classes, especially AI timeout, prompt injection, and failed redaction.
- FR-010 is partially satisfied because logs and artifacts are discussed, but the architecture does not describe exact artifact payload structure, retention enforcement, or a clear mapping from workflow run ID to the final check state across retries and duplicates.
- FR-013 is partially satisfied. The architecture says the redaction service attempts to sanitize obvious secrets and aborts if not safe, but it does not define a fail-closed algorithm or how it detects a secret that appears in a repo diff but not in a conventional format.
- NFR-002 is conceptually addressed through fingerprinting, but the actual branch-head revalidation and stale-run rejection are under-specified.
- NFR-008 is not fully addressed because the architecture does not define safeguards against prompt injection or adversarial file content influencing AI output.

### Conclusion

The architecture is close to the intended behavior but still assumes too much of the surrounding GitHub repository configuration and too little of the AI boundary. It is not yet fully ready for implementation planning.

---

## 4. Critical Findings

### DR-001 — Stale PR head can still commit documentation after branch changes

**Severity:** CRITICAL

**Area:** Idempotency and Concurrency

**Problem:**
The architecture describes fingerprinting and a branch re-fetch before commit, but it does not define a hardened rule that a run is invalid if the PR head SHA changed after AI generation started. A stale run can generate documentation from an old diff and still commit to a newer branch state.

**Why it matters:**
This creates a classic race condition: developer pushes new changes while the AI is still generating docs. The stale workflow can commit a document update based on an outdated branch state, causing incorrect documentation to be merged or overwriting newer changes. This is a correctness and data-integrity failure.

**Evidence:**
The architecture states, “Before committing, re-fetch branch head and ensure the input-state has not changed,” but the mechanism is not tied to a deterministic early-abort condition with a precise failure state. The workflow also allows `pull_request` synchronize events without defining how concurrent runs are canceled or stale runs rejected.

**Recommended change:**
Perform the final validation using the exact PR head SHA captured at workflow start and re-check that same SHA immediately before the commit. If the head SHA differs, abort the run, mark the workflow as stale, and do not create a commit. Require the workflow to reject duplicate or stale branch heads before commit creation and before artifact publication.

**Requirement impact:**
FR-005, FR-007, FR-016, NFR-002, FR-001

---

### DR-002 — Approval gating is not sufficiently enforceable in the workflow itself

**Severity:** CRITICAL

**Area:** Human Approval Review

**Problem:**
The architecture says, “The repository must enforce branch protection rules,” but it does not specify an action-level failure when CODEOWNERS is missing, when the approving user is not authorized, or when approval is granted before the final documentation change set. This leaves critical merge-readiness semantics outside the workflow and outside the architecture definition.

**Why it matters:**
If the repository has no CODEOWNERS file, if branch protection is not set, or if approval is granted before the latest commit, the architecture can create a false sense that human approval is enforced when it is not. That creates a bypass path for merge-ready documentation without required review.

**Evidence:**
FR-008 states, “If no CODEOWNERS exists, the check must fail and the report must require CODEOWNERS configuration.” The architecture describes branch protection as a repository responsibility without a workflow-level guard when that configuration is absent or invalid.

**Recommended change:**
The workflow must explicitly fail when no valid CODEOWNERS entry covers the changed docs or when repository policy does not require CODEOWNERS review. It must also record the PR review state as a distinct workflow step, not as an inferred state. The architecture should require repository configuration to be validated before any documentation commit is considered merge-ready.

**Requirement impact:**
FR-008, FR-007, FR-009

---

## 5. High-Severity Findings

### DR-003 — AI prompt injection and file-scope misuse remain unresolved

**Severity:** HIGH

**Area:** AI Safety Review

**Problem:**
The architecture allows the AI to act on a minimally assembled corpus but does not define a strict allowlist of editable files, a prompt-injection defense strategy, or a guarantee that generated output cannot write outside documentation scope.

**Why it matters:**
A malicious repository file, README, or OpenAPI description could embed instructions designed to coerce the model into generating non-documentation output or rewriting files outside the intended scope. Even if the output is later validated as Markdown, it could still alter or delete unrelated files if the commit step is too permissive.

**Evidence:**
The architecture says the generator “returns candidate documentation diffs,” but it does not limit that generation to a controlled set of doc paths or validate the file list before commit. The requirement explicitly says docs must be generated for supported documentation types, but no allowlist is defined.

**Recommended change:**
Restrict the AI to a fixed set of documentation paths, validate each generated file path before commit, and reject any output that targets non-documentation files. Treat repository content as untrusted input and apply explicit prompt-injection sanitization before external AI calls.

**Requirement impact:**
FR-004, NFR-001, NFR-008

---

### DR-004 — Validation is not strong enough to detect semantic drift in generated docs

**Severity:** HIGH

**Area:** Validation Review

**Problem:**
The architecture distinguishes pre-generation and post-generation validation, but it does not define a deterministic semantic check that verifies that generated documentation matches actual source changes. It relies on human review for semantic correctness instead of a required automated check where determinable.

**Why it matters:**
An AI could generate an incorrect endpoint, omit changed fields, or invent API behavior that is not present in the code. This would pass Markdown lint and link checks while still being wrong. That is exactly the failure mode the requirements seek to prevent with structural consistency checks and human review.

**Evidence:**
The validation section says structural checks are performed “where determinable,” and the architecture explicitly relies on CODEOWNERS review for semantic correctness. This is not enough to protect against a wrong-but-plausible generated documentation patch.

**Recommended change:**
Define deterministic semantic validators: ensure every documented endpoint exists in the code/OpenAPI, every changed parameter is represented, and every removed field is documented as removed or not documented by policy. Fail generation if these checks cannot be satisfied and the repository cannot prove the output matches the actual contract.

**Requirement impact:**
FR-007, FR-009, FR-016, NFR-008

---

### DR-005 — Secret redaction is under-specified and may fail closed too late

**Severity:** HIGH

**Area:** Security Review

**Problem:**
The architecture uses “attempt to redact obvious secrets” before AI calls, but it does not define what qualifies as a secret, how false positives are handled, or what the workflow does when a diff contains an unknown secret pattern or a secret embedded in a file that is not easy to sanitize.

**Why it matters:**
A secret that is not in a recognized pattern could still be sent to the AI provider. This is a direct security violation and may result in secret exfiltration. Conversely, a workflow that only redacts near-current patterns but fails to scan every changed file could produce both false positives and false negatives.

**Evidence:**
FR-013 is explicit: “If safe sanitization is not possible, do not send that content and report the limitation.” The architecture restates this requirement but does not specify the scanning algorithm or fail-closed behavior on partial redaction.

**Recommended change:**
Define redaction as a fail-closed scan of all relevant file content, not just obvious examples. Redact known secret-bearing patterns, normalize candidate values, and block all external AI calls if any unredacted secret candidate remains in the transmitted corpus.

**Requirement impact:**
FR-013, NFR-001, NFR-007

---

## 6. Medium-Severity Findings

### DR-006 — The 10-minute runtime plan is not enforceable enough for large PRs

**Severity:** MEDIUM

**Area:** Runtime and Scalability Review

**Problem:**
The architecture says the workflow should fail gracefully when the 10-minute limit is reached, but it does not define a deterministic timeout budget for each phase or a safe stopping point for AI/validation/retry operations.

**Why it matters:**
The pipeline may spend most of its time in AI generation and retries, leaving insufficient time for validation and commit. Under load, the result becomes nondeterministic and can leave the repo in an unhelpful state without a clear error classification.

**Evidence:**
FR-015 requires maximum runtime of 10 minutes and graceful failure. The architecture describes timeouts in general terms but does not bind each stage to a hard time budget or an artifact-complete failure state.

**Recommended change:**
Assign per-phase budgets (change detection, validation, AI generation, commit, artifact upload), enforce them with explicit timeout handling, and record the partial state in the artifact so that a timeout does not masquerade as a validation failure.

**Requirement impact:**
FR-015, NFR-003, FR-009

---

### DR-007 — Retry semantics can create duplicate or conflicting AI calls under event storms

**Severity:** MEDIUM

**Area:** Reliability and Concurrency Review

**Problem:**
The architecture allows a retry on transient 5xx errors and mentions duplicate prevention, but it does not define how retry state is tracked across multiple event triggers or concurrent PR updates.

**Why it matters:**
An event storm or duplicate `pull_request` events can cause multiple workflow runs to launch concurrently. If the run IDs and deduplication keys are not anchored to the exact PR head and canonicalized diff, multiple AI calls and duplicate commits become possible.

**Evidence:**
The architecture includes a deduplication strategy, but it does not define the precise retry and deduplication keying semantics across repeated events and stale branches.

**Recommended change:**
Use a single deduplication key derived from PR number + head SHA + canonicalized changed inputs. Retry only when the same key is still valid and before any commit is attempted. Track retry count explicitly in the artifact and logs.

**Requirement impact:**
FR-012, NFR-002, FR-010

---

## 7. Low-Severity Findings

### DR-008 — Diagnostic artifact contract is not precise enough for incident response

**Severity:** LOW

**Area:** Observability Review

**Problem:**
The architecture names the required metrics but does not define exact artifact structure, naming, or how validation and retry metadata are serialized.

**Why it matters:**
Without a deterministic artifact schema, debugging failed runs becomes harder, and operators may miss the true reason for a failure or whether the action was stale, rejected, or timed out.

**Evidence:**
FR-010 requires workflow run ID, run duration, number of AI calls, validation status, artifact link, and retention. The architecture mentions these requirements but not their exact output format.

**Recommended change:**
Define a single artifact manifest with required fields, stable filenames, and a machine-readable summary plus a human-readable PR check summary.

**Requirement impact:**
FR-010, NFR-006

---

## 8. Adversarial Scenario Results

The architecture was evaluated against the required adversarial scenarios.

1. PR changes an API endpoint.
   - Partially handled. The change detector and impact analyzer are designed to detect API changes, but the architecture needs a stronger semantic verification step to ensure the generated docs match the actual endpoint contract.

2. PR changes only internal implementation details.
   - Handled. The impact analyzer should determine that no externally visible docs are affected and avoid unnecessary generation.

3. PR changes only documentation.
   - Handled. The architecture can skip generation if doc-only changes do not require synchronization.

4. PR changes an OpenAPI specification into an invalid state.
   - Partially handled. Pre-generation validation catches malformed OpenAPI in theory, but the architecture should be explicit about blocking generation and failing the action before any AI call.

5. AI returns invalid Markdown.
   - Partially handled. Markdown linting is a post-generation validator, but the design should specify whether invalid output is quarantined before commit and what artifacts are produced.

6. AI returns an incorrect endpoint.
   - Not handled well. This requires a deterministic semantic check beyond formatting and link validation.

7. AI call times out.
   - Partially handled. The architecture mentions retries and timeouts, but the phase budgeting and final failure state are not explicit enough.

8. AI returns HTTP 500.
   - Handled in principle via a single retry on transient 5xx errors.

9. AI authentication fails.
   - Handled in principle, but the architecture should explicitly classify it as a deterministic error and not retry.

10. Secret appears in changed source code.
   - Partially handled. The design assumes the redaction layer catches it but does not define exhaustive detection or fail-closed behavior.

11. Secret cannot be safely redacted.
   - Handled in principle, but must fail before the AI call and include a precise artifact summary.

12. Two workflow runs process the same PR simultaneously.
   - Not fully handled. The design does not explicitly define which workflow wins or how stale runs are discarded.

13. PR receives a new commit while AI generation is running.
   - Not fully handled. The architecture needs a strict head-SHA check before commit, not merely before commit preparation.

14. Documentation commit triggers another workflow run.
   - Partially handled. It is expected, but the architecture does not define how detached or stale duplicate runs are treated.

15. Two generated commits race to update the same branch.
   - Not handled adequately without a head-SHA revalidation plus commit lock or fail-fast behavior.

16. CODEOWNERS is missing.
   - Partially handled. FR-008 requires failure, but the architecture relies on repository configuration rather than an explicit workflow gate.

17. An unauthorized user approves the PR.
   - Partially handled. Native GitHub review flow can enforce it, but the workflow must explicitly check the approval origin and repository policy.

18. CODEOWNER approval exists and then new changes are pushed.
   - This is not explicitly handled. The architecture needs to state that approval is invalidated by new commits, which is a native GitHub behavior but must be reflected in the workflow state.

19. Validators fail after AI generation.
   - Handled in principle, as post-generation failure must prevent the commit.

20. Relevant tests cannot be determined.
   - Handled in principle, as the architecture states it must report the limitation.

21. Relevant tests fail.
   - Partially handled. The architecture mentions relevant tests but not the exact fail/skip policy for doc-only changes or untestable scopes.

22. GitHub API fails during commit.
   - Partially handled. A commit action can fail, but the architecture does not define whether to retry automatically or fail the check while preserving state.

23. Artifact upload fails.
   - Partially handled. The architecture states artifacts are uploaded, but not under which conditions the check should be marked failed versus warning only.

24. Workflow approaches the 10-minute timeout.
   - Not sufficiently handled. The architecture needs phase-specific budgets and a deterministic timeout policy.

25. A malicious repository file attempts prompt injection.
   - Not sufficiently handled. There is no explicit defense against prompt injection in the AI boundary.

26. Generated documentation attempts to modify a non-documentation file.
   - Not sufficiently handled. There is no explicit allowlist or path validation before commit.

27. A stale workflow attempts to commit after the PR head changed.
   - Not handled well enough. This is the core concurrency gap in the current architecture.

28. The same documentation output is generated twice.
   - Partially handled. The architecture mentions deduplication, but it does not define a strong, deterministic key and commit existence check across retries and parallel runs.

---

## 9. Security Review

The architecture is generally cautious about secrets and minimal permissions, which is positive. The explicit use of GitHub Actions secrets, the limited permission set, and the requirement to keep diagnostic artifacts private align with the security requirements.

The unresolved security risks are concentrated in the AI boundary and the commit boundary:

- Prompt injection from repository content remains a genuine risk because the architecture does not define explicit sanitization of user-controlled file contents before sending them to the external AI provider.
- Secret redaction is not defined as a fail-closed system that scans all relevant content and blocks transmission if any secret candidate remains.
- The architecture allows generated output to be committed without a strict file-path allowlist, which could permit unintended modifications if the model generates changes outside supported documentation files.
- The design asserts that OpenAI is the only external provider but does not describe how network egress is restricted or how responses are validated before they are applied to the repo.

This architecture mitigates low- and medium-level secrets leakage risk through redaction and least-privilege permissions, but it does not fully eliminate the risk of prompt-injection or a model-generated file-scope violation.

---

## 10. Reliability and Concurrency Review

The architecture is structurally modular and references determinism, but the concurrency model is not yet hardened enough for production use.

The strongest issue is the lack of a robust stale-run and branch-head model. The design states that a final branch re-fetch occurs before commit, but there is no explicit guarantee that the same workflow run has not been superseded by a newer commit. That leaves an unbounded window where the action can commit outdated docs.

The architecture also does not define the behavior when two workflow runs start from the same PR head, when a new commit arrives during generation, or when another run already created a doc commit. The result is a race condition that can generate duplicate results or stale outputs.

This architecture is acceptable as an initial concept, but not as a final design for a workflow that is expected to be safe under concurrent PR updates.

---

## 11. Validation Review

The architecture includes important validation stages, which is a strength. Pre-generation and post-generation validation are both described, and they align with FR-007, FR-009, and FR-016.

However, the validation model is not yet fully deterministic or sufficiently comprehensive:

- OpenAPI syntax validation is defined but not tied to a precise failure criterion for the generated result.
- Markdown lint and link validation are treated as generic validators, but they do not guard against endpoint-level semantic drift.
- Structural consistency checks are only “where determinable,” which is an acceptable statement but not a strong architectural requirement for correctness.
- The design does not define what to do when tests cannot be determined and there is no path to proving the generated docs are correct.

The architecture should not treat AI-generated documentation as trusted input even when it is syntactically valid. Validation must block incorrect output before it becomes a commit, not merely leave it to human review.

---

## 12. Human Approval Review

The architecture correctly uses native GitHub review and CODEOWNERS as required. This is the right design choice and the best way to satisfy FR-008 without inventing a custom approval-monitor service.

The weakness is that the architecture does not specify the exact failure semantics around missing CODEOWNERS or stale approval. The workflow needs to be explicit that:

- the check fails if any required CODEOWNERS review configuration is absent,
- approval is invalidated when new commits are pushed,
- a successful automated check is not considered mergeable by itself,
- merge readiness requires both automated validation and a valid CODEOWNERS review.

If these semantics are left implicit, the architecture can fail in real repositories where branch protection and CODEOWNERS policies differ.

---

## 13. Runtime and Scalability Review

The architecture is compatible with the 10-minute constraint on paper, but there is not enough specificity to demonstrate it in production for large PRs.

The architecture identifies large PRs, many changed files, large OpenAPI specs, expensive link checking, and AI latency as risks, but it does not define the per-stage budget or the fallback behavior when the time budget is reached. This is especially important because AI generation and retries can consume a large share of the total runtime and leave no time for required validation.

The system will likely work for small and medium PRs, but it needs explicit time budgets and a clear fail-fast mode for large or ambiguous PRs.

---

## 14. Observability Review

The architecture includes logs and private diagnostic artifacts and cites FR-010 requirements. That is appropriate and consistent with the v1 scope.

The weak point is not in the existence of observability, but in the lack of a precise artifact schema. The requirements specify detailed metrics, but the architecture does not define the exact artifact shape or the mapping from workflow run ID to final check state. Without that, the workflow is harder to diagnose when the failure reason is ambiguous or when retries and deduplication produce multiple runs.

The design should also specify whether a stale run records its outcome as stale, retry, or fail, and whether the artifact includes the exact cause of the rejection.

---

## 15. Traceability Review

The architecture uses requirement identifiers in the component summaries, which is good. The traceability table is reasonably mapped to the approved requirements and the IDs appear to exist in `docs/requirements.md`.

The notable concern is not invalid references but the fact that some requirement IDs are only loosely connected to actual implementation behavior. For example, FR-008 and FR-013 are referenced in the architecture summary but not mapped to a concrete workflow gate or a fail-closed redaction decision. This is a traceability-quality issue, not necessarily a requirement issue.

The relationship chain is generally plausible:

Requirement → Architecture decision → Implementation → Test

but the architecture needs to make the implementation-level enforcement more explicit in order to be robustly traceable.

---

## 16. Recommended Architecture Changes

1. Add a strict stale-run gate using PR head SHA and canonical input fingerprint before any commit is attempted.
2. Formalize the approval model: define the workflow failure when CODEOWNERS is missing, when the approval is invalid, and when the approval predates the latest PR head.
3. Add a path allowlist for generated documentation and reject any non-documentation file mutation.
4. Add a fail-closed secret scanning rule before any external AI call and require documented reasoning when safe sanitization is impossible.
5. Define deterministic semantic checks for generated docs where the API contract can be compared against changes in code or OpenAPI.
6. Add explicit phase budgets for validation, AI generation, retries, and artifact upload to meet the 10-minute runtime requirement.
7. Document the artifact schema and artifact lifecycle clearly, including required fields, retention, and final check state mapping.

These are not new requirements; they are clarifications and enforcement mechanisms to make the existing requirements actually executable and safe.

---

## 17. Review Decision

CONDITIONALLY APPROVED — specific changes required

The design is a credible v1 architecture and aligns with the intended GitHub Action model, but it is not yet complete enough to proceed without tightening the concurrency guardrails, approval semantics, and AI safety boundaries.

The architectural issues are not merely implementation details. They materially affect whether the system can remain correct, safe, and deterministic under real PR traffic.
