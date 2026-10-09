# Bank Statement Extractor

This is a small team of AI agents that reads a bank statement PDF and turns it
into clean, structured data. It also checks its own work, learns from its
mistakes, and shows you everything in a simple web page.

## What it does

- Reads a PDF and pulls out the text.
- Three agents run at the same time. One grabs the customer details, one grabs
  the account details, and one grabs the transaction table.
- A merge step joins those results into one record.
- A validation step checks the numbers add up and the dates make sense.
- If something is wrong, a reflection step writes down what went wrong and how to
  avoid it next time.
- Those lessons are saved. If the same mistake shows up again for the same bank,
  the lesson gets "promoted" into a trusted rule(Semantic memory-long term) and fed back into future runs.
- Every LLM call's tokens and cost are tracked per agent.
- A web page (built with Streamlit) shows all of this live, and lets a person
  approve or reject the final result.

## How the files are laid out

```
app.py                 the web page (Streamlit UI)
pipeline.py            runs the whole thing, one stage at a time
crewai_extraction.py  the extraction and merge agents
validation.py         the rule checks (balances, dates, required fields)
review.py             saves a human-approved result
utils.py              reads the PDF safely and parses JSON from the model
prompts/              one file per agent prompt, with version history
memory/               saves what the system has learned (two tiers)
telemetry/            saves token counts and cost per call
data/statements/      put your PDF statements here
data/approved/        approved results get saved here
```

## Setup

You need Python 3 and an API key.

1. Put your key in the `.env` file. It should look like this:

   ```
   GEMINI_API_KEY = your-key-here
   LLM_MODEL = gemini/gemini-3.5-flash
   ```

   The key is never written into the code. It is only read from `.env`.

2. Install the libraries:

   ```powershell
   pip install streamlit "crewai[google-genai]" PyPDF2 python-dotenv pyyaml
   ```

## How to add a document

Drop a PDF bank statement into the `data/statements/` folder. That folder is the
only place the app is allowed to read from, so files outside it are blocked on
purpose.

## How to run it

Start the web page from the project folder:

```powershell
streamlit run app.py
```

This opens a browser tab. In the sidebar, pick your PDF, type the bank name, and
press **Run**. You will see each stage appear as it finishes.

When it is done you can look at:

- the fields it pulled out, and the transactions as a table
- whether the checks passed or failed
- proof that the three agents really ran at the same time
- how many tokens it used and what it cost
- which prompt version each agent used
- what the system has learned so far (at the bottom of the page)

Then you can press **Approved** to save the result, or **Reject** and describe
what was wrong so the system can learn from it.

## A quick note on running the demo

To see the learning loop in action, take a statement and change one transaction
amount by hand so the math no longer adds up. Run it once and validation will
fail and a lesson gets saved. Run the same broken statement a second time and the
lesson gets promoted into a trusted rule.

## Decision log

A few choices worth explaining:

- **The user types the bank name.** Memory is stored per bank. Letting the person
  pick the bank in the UI is simple and avoids guessing it before extraction.
- **The merge step does not retype the transaction table.** Only the small fields
  go through the merge. The big table is copied back with plain code, so it can't
  get cut off or mistyped.
- **Checks are plain Python, not another AI call.** Balances and dates are math,
  so code is faster, free(No LLM call) and always gives the same answer.
- **A lesson is promoted after it repeats twice** for the same bank. One mistake
  could be a fluke. Twice is a pattern worth trusting.
- **We record who caught a problem.** The automatic checks are tagged
  "validator" and a person's feedback is tagged "human", so the two are never
  confused.

## Known limitation

If the model returns an amount as text like `"$1,234.56"` instead of a plain
number, the table still shows it, but the validation math would fail on it. This
is left as a known limitation for now.
