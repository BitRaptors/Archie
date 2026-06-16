# Archie Development Studio — Work Loop

Run the development loop. Read `.archie/issues/WORKFLOW.md` first — it is authoritative.

1. Run `python3 .archie/studio.py next .` to pick the ticket.
   - `blocked` → surface it to the user and STOP.
   - `continue` → resume the in-progress ticket from its first unchecked `[ ]`.
   - `promote` → start the planned ticket (branch + plan).
   - `idle` → report nothing to do.
2. **Scope & Plan**: read the ticket AND `.archie/blueprint.json` (relevant decisions,
   domain_invariants, pitfalls, components for the touched folders). Create branch
   `<type>/ISS-NNN-<slug>`, run `python3 .archie/studio.py move . ISS-NNN in-progress`,
   write the Plan as a checkbox list annotating which rule/invariant each step
   preserves. **Wait for user approval of the plan.**
3. **Autonomous after approval**: implement step by step. Archie's `pre-validate.sh`
   hook enforces `rules.json` on each edit — on a block, fix using the rule's WHY +
   EXAMPLE. After each checkbox: append Iteration Log, update Last Test Run, mark
   `[x]`, commit `feat(ISS-NNN): <step>`. Capture evidence into `evidence/ISS-NNN/`.
4. **Review**: separate review agent on the diff → Review Notes; `move . ISS-NNN
   in-review`.
5. **Verify**: each acceptance criterion one by one; test touched domain invariants
   concretely; optionally run `validate.py` and `drift.py`.
6. **Close out**: `move . ISS-NNN done`, write the PR description, commit
   `docs(issues): close ISS-NNN`, open the PR.

Stop and ask only for: material plan changes, destructive actions, or 2 consecutive
failed fixes on the same root cause (then set `status: blocked`, write Blocker, stop).
