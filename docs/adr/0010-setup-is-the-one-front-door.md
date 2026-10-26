# 0010. Setup is the one front door for every non-daily job

Status: accepted. Amends [ADR-0005](0005-the-setup-skill-replaces-llms-txt.md).

## Context

A person who wants to add a client, fix a stopped capture or report a problem had no one place
to start. Setup held install steps and the category rules held a second copy of the terms.

## Decision

`setup` opens with five plain choices (new machine, finish a partly set-up machine, add a client,
fix something, report a problem) and routes to the right skill. Two sibling skills carry the
jobs that are not an install: `onboard-client` and `troubleshoot`. Feedback stays inside the
existing `reporting-issues` reference and is drafted and handed over, never sent.

- A client's **Category terms** live on one line in the context file. Rules are compiled from
  it (`category_rules.py --from-context`). Nothing transcribes terms into a candidates file,
  except the route that adopts rules the plugin did not write.
- Install checks and install commands each have one copy (`references/checks.md`,
  `references/install-commands.md`).
- Setup does every step it can. The steps only a person can do are one list in `setup`
  (`What only a person does`), audited in `docs/skills/setup/human-only-audit.md`.
- No shipped skill asks for a credential in chat or prints one.
- `daily` does not grow: it stays under the 5,000-word ceiling.

## Why

One front door means a user never has to know which skill to call. One home for terms means a
changed term cannot leave a second copy behind. Names are plain verbs for the job.

## Cost

Two more skills to ship and keep under the size bar; a guard test per rule (see the
`tests/` files named in CONTRIBUTING).
