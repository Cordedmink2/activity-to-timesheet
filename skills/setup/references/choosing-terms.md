# Choosing a client's category terms

The one home of the term-choosing rules. `setup` (the category stage) and `onboard-client` cite this file and never copy it. A client's terms are written once, on its **Category terms** line in `Timesheets/.context.md`; the rules are compiled from that file with `category_rules.py --from-context`, so a term that lives only in a conversation is lost at the next rebuild.

## What `--inspect` prints

`--inspect` prints one `RULE` line per category the activity source holds — `[managed]` for the ones this plugin wrote, `[unmanaged]` for the user's own — with the share of recent window titles each matches and an example of what it caught. Above them, one `SEEN` line per profile tag the titles really carry, with the Edge profile it appeared in: those are the client codes as they really appear, so choose from them rather than from what the user remembers. Then one `HOST` line per address the browser titles carry, most-seen first, counted in distinct titles rather than time: these are what a page names its client by when no tag does. A shared host — `dev.azure.com`, `github.com` — is only ever listed with the organisation after it, because bare it is every client's at once.

## Adopting the user's own categories

**Offer to adopt the unmanaged ones, once, as a single list.** Read each rule's name and the titles it caught, work out which client it is for and which of its words are really that client's, and put the whole set to the user **in plain words and in one pass** — "you already have six categories; I read them as Acme from the word ACME, Beta from BetaPortal, …" — never one question per rule. They accept the list, correct the parts that are wrong, or skip adoption entirely. Keep the words that name the client and drop the ones any client's work could produce: `Invoice|ACME|Acme Holdings` adopts as `ACME` and `Acme Holdings`, not `Invoice`.

   **An adopted rule names what it takes over.** Name the existing category with `--adopts "Acme=Work>Acme"` on the `--from-context` run (the client, then the name exactly as the `RULE` line printed it, — the name exactly as the `RULE` line printed it, `>`-joined if nested). Say it once for each adopted rule. Without that the compiler has no way to know the old rule and the new one are the same rule, and the user ends up with both. `[managed]` rules need no `adopts`: the rebuild replaces them whole, including every rule an older version of this plugin wrote.

   What they accept is written into `Timesheets/.context.md` in step 4, with every other term — the rules are rebuilt from each client's **Category terms** line, so a term that lives only in this conversation is dropped by the next rebuild.

   What they skip is left exactly as it is and goes on working, below the rules you write. **A rule the inspect marked `OVER the … ceiling` is worth raising by name** while you have their attention: it matches a large share of everything they do, and since the first matching rule wins it is taking the label off whichever rule should have won.

## Choosing the terms

**Choose each client's terms with the user — up to eight, and usually two to four.** In this order:
   - **the client code** — `ACME`. It is in the profile tag, in the name of a browser profile kept for the client, and usually in the workspace or folder the user opened for them, so one term catches all three. Where the code is also an ordinary word — `LEDGER`, `NIMBUS` — use its tag, `[LEDGER]`, instead: the bare word turns up in pages that have nothing to do with the client. A code made up in this interview for an untagged client is in none of those places yet: offer it as a term only where the `HOST` lines or the user's own folders already carry it, and keep it in the context file either way;
   - **the names of the client's own products or apps** — the system you build for them, the name their app goes by (`AcmePortal`);
   - **the client's full name**, where it differs from the code;
   - **the addresses only this client's work opens**, from the `HOST` lines — its SharePoint site (`acmetrust.sharepoint.com`), its DevOps organisation (`dev.azure.com/acme-it`), its CRM environment (`acme-uat.example.com`), its own website. These carry the client for a user whose one profile holds every client, and they are worth offering to a tagged user too, for the pages they open outside that client's profile. Read each one back to the user in plain words — "the Acme Trust SharePoint site" — rather than as an address.

   Nothing any other client's work could produce: no domain words (`Invoice`, `Timesheet`), no product any client could be using (`Dynamics`, `SharePoint`, `Xero`), no application names, and no address shared by every tenant (`go.xero.com`, `app.asana.com`) or opened by the user's own firm (round 1). A client's own tenant on a shared product is theirs; the product's name is not. A term is a literal word, matched without case anywhere in the app name or the title, so write it as the user would say it — never a pattern.

## What the compiler refuses

A client with more than eight terms, or none, and a term that matches an implausible share of the sampled titles. Fix the **Category terms** line and run again.
