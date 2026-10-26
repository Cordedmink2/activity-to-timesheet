# Setup human-only audit (guided-setup T2, spike S1, US-2/AC-1)

**Hypothesis (written before the step bodies were read):** setup asks a person to act in four
places only: a browser-store Add click, an administrator prompt, a consent page, and a
credential in the configuration dialog. Every other step is something the agent can do.

**Method:** read-only. Steps 1-7 and "Before you start" in `skills/setup/SKILL.md`, and the
references they cite. Nothing was installed and no host was touched. `Y` = only a person can
do it, `N` = the agent does it, `PENDING-REAL-WINDOWS` = CI cannot drive it and no Windows
host is reachable. The source column is a phrase that is in the skill; a test checks it.

**Result:** the hypothesis missed one place. Step 3 has the person type a title format on an
extension's options page, and the extension has no way to be set from outside. It is now on
the human-only list.

| Step | Human-only? | Source | What |
|---|---|---|---|
| Before you start | N | `Look the rest up yourself rather than asking` | The agent probes configuration, interpreter, shell and activity source itself. |
| Before you start — install | Y | `The administrator prompt is one of the steps in "What only a person does"` | Accepting an administrator prompt, for an install that already needs one today. |
| Step 1 | N | `if "Before you start" installed it, launch it` | The agent installs and starts ActivityWatch; the person only accepts the admin prompt above. |
| Step 2 | Y | `click **Add to** (or **Get**)` | The store gives no way to add an extension for them; the agent opens the page in the right profile. |
| Step 3 | Y | `Click **Save**.` | Typing and saving the title format on the extension's options page. Listed as a new finding. |
| Step 4 | N | `This step is yours, not the user's.` | The agent writes the context file and the rules. |
| Step 4 — refused write | Y | `Add one category for each client.` | Only where this ActivityWatch build refuses the write; said out loud first. |
| Step 5 | N | `registers one scheduled task` | The agent registers the task. The registration itself on a real Windows host is PENDING-REAL-WINDOWS. |
| Step 6 | N | `That one command is the whole check` | The agent runs the calendar check. |
| Step 7 | N | `Install only what the user says yes to.` | A yes or no is the only thing asked; the agent installs. A real consent page or dialog is PENDING-REAL-WINDOWS. |
| Human: Click Add | Y | `**Click Add** on a browser-store page.` | Click Add |
| Human: Administrator prompt | Y | `**Accept an administrator prompt**` | Accept an administrator prompt |
| Human: Consent page | Y | `**Accept a consent page**` | Accept a consent page |
| Human: Credential | Y | `**Put a credential in the configuration dialog**` | Put a credential in the configuration dialog |
| Human: Title format | Y | `**Save a title format** in the extension's options page` | Save a title format |
| Human: Category by hand | Y | `**Type a category by hand**` | Type a category by hand |

## Agent-doable changes found

None new. The agent already does steps 1 (after the admin prompt), 4, 5, 6 and 7 itself.
