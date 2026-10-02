# Autonomous Implementation Execution

You are now executing Phase 6 of the Automated Documentation Sync project.

Your objective is to implement the approved implementation plan completely and safely.

## Source Documents

Read these before making implementation changes:

1. `docs/requirements.md`
2. `docs/architecture.md`
3. `docs/design-review.md`
4. `docs/impl-plan.md`
5. `pyproject.toml`
6. current repository source
7. current repository tests

Then read:

`.github/agents/implementation-agent.agent.md`

Follow that agent definition as the execution policy.

---

## Mission

Execute the implementation plan from:

`TASK-001 → TASK-011`

autonomously.

Do not wait for the human to tell you:

> "Now implement TASK-002."

You must determine the next task yourself from the implementation status and implementation plan.

For every task:

```text
read task
→ verify dependencies
→ implement
→ test
→ diagnose failures
→ repair when safe
→ retest
→ run regression tests
→ verify acceptance criteria
→ verify architecture
→ verify security
→ mark VERIFIED
→ continue
```

---

## First Action

Before implementing TASK-001:

1. Inspect repository status.
2. Read all source-of-truth documents.
3. Validate that the implementation plan is internally consistent.
4. Validate task dependencies.
5. Inspect the existing test configuration.
6. Create or initialize:

`docs/implementation-status.md`

If the implementation plan contains a contradiction that affects implementation semantics, stop and mark:

`HUMAN_REQUIRED`

Do not guess.

---

## Autonomous Execution Rules

You may:

* create source files
* modify source files
* create tests
* modify tests when necessary
* modify explicitly required workflow/configuration files
* run tests
* run linters/type checks already configured by the project
* diagnose failures
* repair implementation defects
* update `docs/implementation-status.md`

You may not:

* change requirements
* change architecture
* change design-review decisions
* rewrite the implementation plan
* weaken tests
* bypass failing validation
* bypass security controls
* introduce unapproved infrastructure
* create a custom approval service
* approve pull requests
* merge pull requests
* force-push

---

## Self-Repair

For a failing task:

1. Diagnose the failure.
2. Identify root cause.
3. Make the smallest safe fix.
4. Re-run targeted tests.
5. Re-run regression tests.

Maximum:

`3 repair attempts per task`

After that:

`HUMAN_REQUIRED`

Do not enter an infinite repair loop.

---

## Progress

Update:

`docs/implementation-status.md`

throughout execution.

The status file must always make it possible for a human reviewer to determine:

* what task is running
* what has been completed
* what tests passed
* what failed
* what was repaired
* what remains
* why execution stopped if blocked

---

## Completion

Do not stop merely because the code compiles or tests pass.

Every task must pass its:

* implementation gate
* test gate
* acceptance-criteria gate
* architecture gate
* security gate
* repository-hygiene gate

Only then mark it:

`VERIFIED`

After TASK-011, execute the complete final verification described by the implementation agent.

Then produce the final implementation report.

Begin.
