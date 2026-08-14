# Assignment — Build a Self-Critiquing, Multi-Agent Document Extractor

## What you're building

A pipeline that reads a messy, multi-page PDF (we use bank statements — dense
tables, inconsistent formatting, numbers that have to add up correctly) and turns
it into clean structured data, using a *team* of small AI agents instead of one
big prompt. Some agents work at the same time (parallel), some run one after
another (sequential), one agent double-checks the others' work, and if it finds a
mistake, the system **remembers the correction** so it doesn't repeat it on the
next document from the same source.

If you finish this assignment, you'll have hands-on experience with the four
things that separate a "call an LLM in a loop" script from a real agentic system:

1. **Orchestration** — deciding what runs in parallel vs. in sequence, and why
2. **Verification** — an agent (or rule) that checks another agent's output before
   you trust it
3. **Memory** — a system that gets better across runs, not just within one run
4. **Observability** — knowing what something cost and why it did what it did

This is deliberately scoped to be buildable by one person in stages. Nothing here
requires a framework you've never heard of — you'll use plain function calls, a
JSON file or two, and (if you want it) a multi-agent library. Framework choice is
up to you (see "Choosing your tools" below).

---

## Learning objectives

By the end of this assignment you should be able to:

- Explain the difference between running LLM calls **sequentially** vs. **in
  parallel**, and correctly identify which parts of a pipeline can and can't be
  parallelized
- Design a **fork/join** pipeline: split work across independent workers, then
  wait for all of them before continuing
- Build a **self-critique loop**: have one LLM call check another's output against
  concrete, programmatically-checkable rules (not just "does this look right?")
- Design a **two-tier memory system** (per-event vs. generalized-rule) and decide
  when something graduates from one tier to the other
- Track **token usage and cost per LLM call**, attributed to the specific agent
  that made it
- Version your **prompts** the same way you version code, with a record of *why*
  each version changed
- Add a **human-in-the-loop** checkpoint that can override or confirm what the
  automated system decided
- Recognize and defend against the specific failure modes that show up in
  real multi-agent document pipelines (see the Edge Cases section — this is
  the part most tutorials skip, and it's where you'll actually learn something)

---

## Prerequisites

- Comfortable writing Python functions, working with JSON, and reading a stack
  trace
- An API key for an LLM provider (Anthropic Claude, OpenAI, or similar) — ask
  your instructor which one this course is standardized on
- `pip install`-level familiarity; you'll be managing a small `requirements.txt`
- You do **not** need prior experience with any agent framework — if you've never
  used one, part of this assignment is picking one and reading its docs

---

## Choosing your tools

You have two valid paths. Pick one before you start:

| Path | What it means | Good if... |
|---|---|---|
| **A — Manual orchestration** | You call the LLM SDK directly (e.g. the Anthropic SDK) and write your own functions to run agents in parallel (Python `threading` or `asyncio`) and pass results between them | You want to deeply understand what "an agent" actually is under the hood, with nothing hidden |
| **B — Agent framework** | You use a multi-agent library (e.g. CrewAI, LangGraph) that gives you `Agent`/`Task` objects and an execution engine | You want to focus on pipeline *design* rather than plumbing, and you're willing to spend time reading that framework's docs carefully |

Whichever you pick, **read the framework's actual source or docs for how
"parallel" execution really works before you rely on it.** Frameworks vary a lot
here — some use real OS threads, some use `asyncio` tasks, some fake concurrency
and just run things one after another behind a parallel-looking API. You will be
asked to prove, with evidence (not just an assumption), that your "parallel"
stage is actually running concurrently. See Milestone 3.

---

## The domain: why bank statements

A bank statement is a good stress-test for document extraction because it has,
in one document:

- **Structured header data** (account number, dates, balances) — a handful of
  scalar fields, easy
- **A large repeating table** (the transaction list) — potentially 50-200+ rows,
  the part most likely to hit token limits or get truncated
- **Internal math that must be self-consistent** — running balances that must add
  up, an opening balance + credits - debits that must equal the closing balance —
  which gives you a way to *validate* extraction quality without a human checking
  every field by hand
- **Wildly different layouts bank-to-bank** — no two banks format statements the
  same way, which is exactly the kind of variation that makes "memory of what
  this specific source looks like" valuable

You can substitute a different document type (invoices, insurance claims,
medical intake forms, receipts) if your instructor allows it — the requirements
below are written generically enough to transfer. If you do, make sure your
chosen document type has at least one **internally-verifiable numeric or logical
constraint** (something a validation step can check without a human), or
Milestone 5 won't have anything real to do.

---

## Architecture overview

```
   Source document (PDF)
            │
            ▼
 ┌─────────────────────────────────────────────┐
 │  STAGE 1 — Parallel extraction (N agents)    │   <- fork
 │  each agent owns a different slice of fields │
 └─────────────────────────────────────────────┘
            │  (wait for every agent to finish)
            ▼
 ┌─────────────────────┐
 │ STAGE 2 — Merge      │   <- sequential
 └─────────────────────┘
            ▼
 ┌─────────────────────┐
 │ STAGE 3 — Validate   │   <- sequential, rule-based checks
 └─────────────────────┘
            ▼
      all checks pass? ──yes──> done, show result
            │ no
            ▼
 ┌───────────────────────────────┐
 │ STAGE 4 — Reflect (self-       │   <- conditional
 │ critique) → write to memory    │
 └───────────────────────────────┘
```

Six logical roles total, three of which run concurrently. That's the shape you're
building. Everything else in this assignment (memory, telemetry, prompt
versioning, UI, human review) wraps around this core.

---

## Milestones

Work through these in order — each one builds on the last, and later milestones
assume earlier ones work. Each milestone has a **Goal**, **Definition of done**,
**Hints**, and **Check yourself** questions. The hints tell you *what to think
about*, not the answer — resist the urge to look for exact code online before
you've tried designing the function signature yourself.

### Milestone 0 — Project skeleton & safe file handling

**Goal:** Set up config loading and a PDF text-extraction utility you'll reuse
everywhere.

**Definition of done:**
- Environment variables (API key, endpoint, model name) load from a `.env` file,
  never hardcoded
- A function that takes a PDF path and returns its full text content
- That function **refuses to read a path outside an allowed directory**

**Hints:**
- Look up `python-dotenv` for the `.env` loading, and a PDF text library
  (`PyPDF2`, `pdfplumber`, or similar) for extraction — multi-page PDFs need every
  page's text joined, not just the first
- For the path-safety requirement: think about what happens if the PDF path came
  from a web form or CLI argument that a user controls. What's `../../etc/passwd`
  going to do to a naive `open(path)` call? Resolve the path to an absolute form
  and check it starts with your allowed base directory *before* opening it.

**Check yourself:**
- What happens to your extraction function if you feed it a PDF where a page is a
  scanned image with no embedded text layer? (You don't have to fix this — but
  you should know your function's behavior here, and document it.)

---

### Milestone 1 — One extraction agent, end to end

**Goal:** Before building three parallel agents, get *one* agent working
end-to-end: it reads document text, calls the LLM, and returns structured data.

**Definition of done:**
- One agent with a clear, narrow job (e.g. "extract just the account holder's
  name and address")
- A prompt template that tells the model exactly what fields to return and in
  what JSON shape
- A function that takes the model's raw text response and reliably parses it
  into a Python dict — even when the model wraps its answer in explanation text
  or markdown code fences

**Hints:**
- LLMs asked for JSON frequently still wrap it in ```` ```json ... ``` ```` fences,
  or add a sentence before/after. Your parser needs to strip that, not just call
  `json.loads()` on the raw string and hope.
- Put the expected output shape *directly in the prompt*, as literal example
  JSON with placeholder types (`"date": "YYYY-MM-DD"`) — vague instructions like
  "return the data as JSON" produce inconsistent shapes across runs.
- Decide now what field names your JSON schema uses everywhere (`date` vs
  `transaction_date`, `debit` vs `amount_out`) — you'll be merging multiple
  agents' output later, and mismatched field names between agents are a
  surprisingly common self-inflicted bug.

**Check yourself:**
- What does your parser do if the model returns text that *isn't* valid JSON at
  all (e.g. it refused, or explained instead of answering)? Does your code crash
  with an unhandled exception, or fail in a way you can see and debug?

---

### Milestone 2 — Split into parallel extraction agents

**Goal:** Split the single agent from Milestone 1 into 3 (or more) agents that
each own a *non-overlapping* slice of the document's fields, and run them
concurrently.

**Definition of done:**
- At least 3 agents, each with a distinct, narrow responsibility (e.g. account
  metadata / customer identity / transaction table)
- All three genuinely execute **concurrently**, not one after another
- You have **proof** they ran concurrently — not just an assumption. (Timestamps
  logged at the start and end of each agent's call, printed or stored, showing
  overlapping time ranges, is the simplest proof.)

**Hints:**
- If you're on Path A (manual), `threading.Thread` (LLM calls are I/O-bound —
  waiting on a network response — so Python's GIL isn't the obstacle it would be
  for CPU-bound work) or `asyncio.gather` both work. Pick one and understand why
  it achieves concurrency for *this specific kind of work*.
- If you're on Path B (framework), find the specific flag/parameter that marks a
  task as safe to run concurrently, and **read what it actually does** before
  trusting it. Some frameworks' "parallel" tasks still block the same way a
  sequential one would unless you look closely at how the executor is built —
  this is exactly the kind of thing that looks right in a demo and silently isn't
  in your actual pipeline. Don't take a framework's marketing claim at face
  value; check the mechanism.
- Whatever you build, you need an explicit **join** point — a place in the code
  that blocks until *all* parallel agents are done before the next stage starts.
  Where is that in your code? Can you point to the line?

**Check yourself:**
- What happens if agent 2 takes 10x longer than agents 1 and 3 (e.g. it's
  processing a much bigger table)? Does your join logic correctly wait for the
  slow one, or does it move on with incomplete data?
- What happens if one of the three agents raises an exception mid-flight? Does it
  take the whole pipeline down, or can you isolate the failure?

---

### Milestone 3 — Merge the parallel results

**Goal:** Combine the independent outputs from Milestone 2 into one unified
record.

**Definition of done:**
- A merge step that takes N partial JSON results and produces one combined JSON
  object matching a single target schema
- It does **not** silently drop or overwrite fields when two agents disagree

**Hints — this is the milestone with the sharpest trap in it:**
- If one of your parallel agents extracts a *large* table (like the transaction
  list), think hard before having your merge step ask the LLM to **retype that
  entire table** into its own output alongside the other fields. Two things go
  wrong: (1) large generated arrays are exactly what gets cut off when a response
  hits its token limit, producing broken JSON; (2) even when it doesn't truncate,
  you're paying an LLM to copy data it already extracted correctly once,
  introducing a new chance for transcription errors.
- Consider instead: have the merge step's LLM call handle only the *small*
  fields (the ones actually in conflict or needing reconciliation), and splice
  the large table field back in afterward using plain code from the original
  agent's output — no LLM in that path at all.
- This is a real design decision with a real tradeoff, not a trick question —
  try it the naive way first if you want to see the failure yourself before
  fixing it. (Feed it a document with 100+ rows and watch what happens to your
  merge step's output token count and JSON validity.)

**Check yourself:**
- If two of your agents extracted the same field differently (e.g. the bank name
  spelled two different ways from two different parts of the document), what
  does your merge logic do? Pick a policy on purpose, don't let it be accidental.

---

### Milestone 4 — Validate the merged result

**Goal:** A step that checks the merged data against concrete, mechanically
verifiable rules — not "does this look plausible" but "does the math/logic
actually hold."

**Definition of done:**
- At least 4-5 distinct checks, each one either objectively pass/fail (not
  subjective)
- Output is a clear `{is_valid, errors: [...]}` shape with enough detail in each
  error to act on it

**Hints:**
- For a bank statement: does every transaction date fall inside the statement
  period? Does the running balance actually add up transaction-by-transaction
  from the opening balance? Does the last computed balance equal the stated
  closing balance? Are required fields (name, address, account number)
  non-empty?
- You can implement these checks as **plain Python** (fast, deterministic, free)
  or as **another LLM call** (more flexible, catches things you didn't think to
  code explicitly, costs money and can be wrong itself). Which one(s) you choose,
  and why, is a real design decision — write down your reasoning.
- Whichever you choose, make sure the checks are things a machine can decide
  *without* a human in the loop — that's what makes the next milestone possible.

**Check yourself:**
- Deliberately feed your validator a document you know has a math error in it
  (edit one transaction amount by hand). Does it actually catch it? If your
  checks are LLM-based, run it twice on the same broken document — does it agree
  with itself both times?

---

### Milestone 5 — Self-critique / reflection loop

**Goal:** When validation fails, run a step that explains *why* it failed and
produces a reusable lesson — not just "here's the error" but "here's what to do
differently next time."

**Definition of done:**
- A conditional step, only triggered on validation failure, that outputs a
  `{mistake_description, correction_rule, confidence}` (or similar) structure
- The `correction_rule` should be **generalizable** — written so that it's useful
  advice for the *next* document from the same source, not just a description of
  this one instance

**Hints:**
- The prompt for this step should be given both the *error* and enough of the
  *original document* to reason about why the mistake happened — "the model said
  X but the actual document shows Y, probably because Z" is the kind of
  reasoning you want, not just "field was wrong."
- Push yourself on the difference between a description and a rule. "The date
  was wrong" is a description. "This bank writes dates as DD/MM not MM/DD — parse
  accordingly" is a rule. Only the second is useful to inject into a future
  prompt.

**Check yourself:**
- Read one of your own `correction_rule` outputs a week from now (or hand it to
  a classmate) with zero other context. Would they understand what to do
  differently? If not, your reflection prompt needs to ask for more specificity.

---

### Milestone 6 — Two-tier memory (episodic + semantic)

**Goal:** Persist corrections so future runs benefit from past mistakes, with two
tiers: a raw log of individual events, and a smaller set of generalized, trusted
rules promoted from repeated events.

**Definition of done:**
- **Episodic memory**: every reflection from Milestone 5 gets appended to a
  persistent store (a JSON file is fine), tagged with which document *source*
  (e.g. which bank) it came from
- **Semantic memory**: a separate store of generalized rules, where a rule only
  appears once a *similar* correction has been logged episodically more than
  once for the same source
- A function that formats relevant memory (semantic rules first, falling back to
  recent episodic entries) as a text block to inject into your extraction
  prompts

**Hints:**
- Key everything by document **source** (bank name, vendor name, whatever's
  appropriate), not globally — a formatting quirk learned from one source has no
  business affecting extraction of a different source's documents.
- "Similar correction" doesn't require anything fancy. Normalizing text (lowercase,
  collapse whitespace) and comparing for equality is a legitimate, explainable
  starting point — you don't need embeddings or a vector database for this
  assignment. Pick a promotion threshold (how many times does something need to
  repeat before it's "confirmed"?) and be ready to justify the number you chose.
- Think about what happens to memory over a long-running system — does anything
  ever get *removed* from episodic memory, or does it grow forever? You don't
  have to solve this, but you should be able to answer what your current design
  does.

**Check yourself:**
- Run your pipeline against the same (deliberately broken) document twice. After
  the second run, does a semantic rule appear? After it does, run the pipeline a
  third time and check: does the extraction prompt actually receive that rule as
  context? (It's easy to build the promotion logic and forget to wire the
  read-path back into the prompt — verify both directions independently.)

---

### Milestone 7 — Cost and token telemetry

**Goal:** Track how many tokens and how much money each agent call used, and
surface it per-agent and per-run.

**Definition of done:**
- Every LLM call's input/output token counts and estimated cost are recorded,
  tagged with which agent made the call
- A per-run summary (total cost, total tokens) and a per-agent breakdown
- Historical runs are persisted somewhere you can look back at later

**Hints:**
- Check whether your SDK/framework actually attaches token usage metadata to
  every response you receive, in every mode you call it in. **Verify this
  yourself with a real call and print the raw response** — don't assume
  documentation examples cover your exact code path (e.g. streaming vs.
  non-streaming responses can behave differently in some client libraries, and
  the usage field you're expecting can silently come back empty). If it's not
  there, you need a fallback plan — e.g. a dedicated token-counting endpoint or
  library, called against the exact text you sent/received.
- Pricing varies by model and changes over time — look up current pricing for
  the model you're using and don't hardcode a number you're not sure is current.
- Structure your telemetry record shape (agent name / model / input tokens /
  output tokens / cost / timestamp) as if you might swap in a real observability
  platform (Langfuse, Helicone, etc.) later — that constraint alone will push you
  toward a cleaner design than "just print some numbers."

**Check yourself:**
- Sum your per-agent costs. Does the total match your per-run total exactly?
  (If not, you're either double-counting or dropping a call somewhere.)

---

### Milestone 8 — Versioned prompt templates

**Goal:** Treat your prompts as versioned artifacts, not strings buried inline in
your pipeline code.

**Definition of done:**
- Prompts live outside your Python code (e.g. one file per agent role)
- Each prompt has a version number and a changelog entry explaining *why* it
  changed, not just what changed
- Your pipeline records which prompt version was used for each run

**Hints:**
- You don't need a hosted prompt-management product for this — a YAML or JSON
  file per agent, with a `current_version` pointer and a `versions: {1: {...}, 2:
  {...}}` map, is a completely legitimate implementation and keeps every past
  version available for comparison.
- The discipline that matters here isn't the storage format, it's writing a real
  changelog entry *every time you change a prompt* — "why did this need to
  change, what problem was v1 causing" — the same way you'd write a commit
  message. If you go back through Milestone 3's merge-prompt design decision, you
  now have a real example of a changelog-worthy prompt revision to model yours
  on.

**Check yourself:**
- Could someone else on your team look at your prompt version history and
  understand the evolution of your extraction logic without reading your git
  log?

---

### Milestone 9 — UI: show the pipeline live, not just the final answer

**Goal:** Build an interface (a simple web UI is easiest — Streamlit, Gradio, or
similar) that shows each stage of the pipeline as it happens, not just a spinner
followed by a final result.

**Definition of done:**
- The user can pick a document and trigger a run
- The UI shows, in order: the parallel agents completing (with evidence they
  overlapped — reuse your Milestone 2 proof here), the merge result, the
  validation result, and the reflection result *if triggered*
- The transaction/table data renders as an actual table, not a JSON blob
- Cost/token telemetry and prompt versions used are visible somewhere in the UI
- A memory view showing the episodic log and semantic rules, so a user can see
  what the system has "learned" so far

**Hints:**
- Design your pipeline function as a **generator** that yields a status update
  after each stage, rather than one function that blocks until everything is
  done and returns once. This is what lets your UI update live instead of
  showing a single loading spinner for the whole run — the UI loop just consumes
  your generator and re-renders after each yield.
- Keep rendering logic (turning a result dict into UI widgets) as a set of small,
  separate functions — one per section of the screen. It makes the UI code much
  easier to reason about, and easier to test independently of the pipeline.

**Check yourself:**
- Load-test your own patience: run it against a document that's much bigger or
  much messier than your test cases. Does the UI degrade gracefully (clear error
  shown) or does it just hang with no feedback?

---

### Milestone 10 — Human-in-the-loop approval

**Goal:** Add an explicit checkpoint where a human confirms or overrides the
system's output, and make that human decision count.

**Definition of done:**
- An **Approve** action that persists the final, human-confirmed result somewhere
  durable, separate from the raw pipeline output — and if a reflection happened
  automatically this run, marks that correction as **human-confirmed** (not just
  machine-asserted)
- A **Reject** action that lets the human describe what was actually wrong (even
  if automated validation said everything passed) and feeds that into your
  Milestone 5 reflection step, tagged as coming from a human, not the automated
  validator

**Hints:**
- Distinguishing *source* of a correction (automated validator vs. human
  reviewer) in your episodic memory schema matters — a human catching something
  your validator missed is exactly the signal that should make you go back and
  add a new automated check in Milestone 4. Don't let that signal get lost by
  storing it identically to machine-caught corrections.
- Think about what "Approve" should actually *do* to your memory system. If a
  human approves output that includes an unconfirmed reflection entry, should
  that entry's confidence or trust level change? Decide, and implement it
  intentionally rather than leaving it as an accident of whatever you happened
  to build first.

**Check yourself:**
- Can you, days later, look at one entry in your episodic memory and answer:
  was this caught by the validator or by a human, and was it ever confirmed?

---

## Edge cases and robustness checklist

This is the section most tutorials skip, and it's where the real learning is.
Go through every item below **on purpose** — for each one, either (a) demonstrate
your system handles it and explain how, or (b) explicitly document that it's a
known limitation and why you scoped it out. "I didn't think about it" is the only
wrong answer here; a documented limitation is a completely acceptable answer for
a course assignment.

**Input documents**
- [ ] A document with zero pages of extractable text (e.g. scanned image, no
  text layer) — what happens?
- [ ] A document with 3x more rows in the big table than anything you tested
  with during development
- [ ] A document from a source (bank, vendor) your system has never seen before
  — does it still produce a reasonable result with no memory to draw on?
- [ ] A completely empty or corrupted PDF file
- [ ] A path to a file outside your intended data directory (security — see
  Milestone 0)

**LLM output**
- [ ] The model wraps JSON in explanation text or code fences
- [ ] The model's response gets cut off mid-JSON because it hit its output token
  limit (test this on purpose — feed your biggest table-extraction agent a
  document you know is large, with a deliberately small token limit, and observe
  the actual failure)
- [ ] The model returns a value type you didn't expect (e.g. a number formatted
  as `"$1,234.56"` string instead of a plain number — does your downstream code
  that expects numeric types break?)
- [ ] Two parallel agents disagree on a field that should have one true answer

**Concurrency**
- [ ] One parallel agent throws an exception — does it corrupt the results of
  the others, or can you isolate it?
- [ ] Two runs are triggered back-to-back (or by two different users) — do their
  results, telemetry, or memory writes collide with each other?

**Memory**
- [ ] First-ever run against a brand-new source has empty memory — confirm your
  prompt-formatting function handles an empty memory result gracefully instead
  of injecting a broken or confusing string
- [ ] The same mistake is logged for two *different* sources — confirm it does
  **not** get promoted to semantic memory (promotion should be per-source)
- [ ] A correction is logged, then a human later approves output that
  contradicts it — does your system have any way to notice the conflict, or at
  least surface it for review?

**Cost/telemetry**
- [ ] What happens to your cost estimate if `CLAUDE_MODEL` (or your provider's
  equivalent) is changed to a model your pricing table doesn't have an entry
  for? Does it silently show `$0.00`, crash, or fall back to a sane default?
  (Silently wrong is the worst of these three — make sure yours isn't that one.)

**Security / correctness discipline**
- [ ] API keys are never hardcoded or printed in logs
- [ ] Every file path derived from user input goes through your Milestone 0
  path-safety check — audit every place you call `open()` and confirm it
  applies

---

## Deliverables

1. Working code implementing Milestones 0 through 10 (or a documented subset, if
   your instructor scopes it down)
2. A short `README.md` explaining how to run it (env setup, how to add a new
   document, how to launch the UI)
3. A **decision log** (can be a section in the README) — 5-10 short entries,
   each describing one non-obvious choice you made and why. Good candidates: your
   merge strategy from Milestone 3, your memory promotion threshold from
   Milestone 6, your validation checks from Milestone 4, your choice between
   code-based vs. LLM-based validation.
4. Evidence for the Edge Cases checklist — this can be a table in your README
   (`case → handled how / demoed how`), doesn't need to be automated tests unless
   your instructor requires them
5. A short (5-10 minute) live or recorded walkthrough: run your pipeline on a
   document that's designed to trigger a validation failure, and narrate what
   happens at each stage, including the memory write and (if you built Milestone
   9) the UI updating live

---

## Grading rubric (suggested — confirm weights with your instructor)

| Area | Weight | What "excellent" looks like |
|---|---|---|
| Parallel + sequential orchestration (M1-3) | 20% | Genuine, provable concurrency; a clean, deliberate merge strategy that avoids the large-table re-transcription trap |
| Validation quality (M4) | 15% | Checks are concrete and mechanically verifiable; caught a deliberately-broken test document |
| Self-critique loop (M5) | 15% | Correction rules are genuinely generalizable, not just restatements of the error |
| Memory system (M6) | 15% | Both tiers work and are wired to both write *and* read paths; promotion logic is scoped correctly per-source |
| Telemetry (M7) | 10% | Per-agent attribution is accurate; totals reconcile |
| Prompt versioning (M8) | 5% | Real changelog entries, not just version-number bumps |
| UI + HITL (M9-10) | 10% | Live stage-by-stage rendering; Approve/Reject both meaningfully affect stored state |
| Edge case handling & decision log | 10% | Checklist is genuinely worked through, not just checked off; decisions are justified, not arbitrary |

---

## Stretch goals (optional, for extra credit or just curiosity)

- Swap your local telemetry store for a real observability platform (Langfuse,
  Helicone, or similar) — how much of your Milestone 7 design has to change?
- Add a fourth parallel extraction agent for a new field category, and update
  every downstream stage (merge schema, validation, UI) to match — this exercise
  touches literally every layer you built and is a good end-to-end test of how
  maintainable your design actually is
- Replace your exact-match memory promotion (Milestone 6) with a similarity
  threshold based on embeddings — does it actually produce better groupings than
  the plain-text-normalization version, or just different ones? Justify your
  answer with real examples from your own memory log.
- Add a second document type (a different domain entirely) and see how much of
  your pipeline is genuinely reusable vs. how much was secretly bank-statement-
  specific
- Add retry logic with backoff for transient API failures, and a circuit breaker
  if a specific agent fails repeatedly — what should happen to a pipeline run
  that's mid-flight when that triggers?

---

## A note on using AI assistance for this assignment

Using an LLM to help you write code for this assignment is fine and expected —
that's the whole domain you're working in. But the **design decisions** (your
merge strategy, your promotion threshold, your validation rules, your answers to
the "Check yourself" questions) need to be *yours*, and you need to be able to
explain and defend them. The decision log deliverable exists specifically so
you have to articulate your reasoning in your own words — an AI-generated
decision log that you can't explain in the live walkthrough will be obvious, and
graded accordingly.
