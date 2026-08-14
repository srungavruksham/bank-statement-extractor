import streamlit as st
from pathlib import Path
from datetime import datetime

from pipeline import run_pipeline
from memory.store import (
    add_episodic_entry,
    check_for_promotion,
    mark_correction_confirmed,
    load_episodic_memory,
    load_semantic_memory,
)
from review import save_approved_result


# This entire code re-runs top-to-bottom on every interaction
STATEMENTS_DIR = Path("data/statements").resolve()   # this is our allowed directory for PDFs. we don't want to let the user pick arbitrary files on disk.
EPISODIC_FILE = "memory/data/episodic.json"          # same defaults the pipeline uses
SEMANTIC_FILE = "memory/data/semantic.json"

st.set_page_config(page_title="Bank Statement Extractor", layout="wide")
st.title("Bank Statement Extractor")

#remembers the last run's result in session_state so we can show it after the pipeline finishes.
if "result" not in st.session_state:
    st.session_state["result"] = None


# ---- render helpers: one small function per area of the screen --------------

def render_merged_fields(merged_data):
    # everything except the big transactions list is a simple scalar field
    scalars = {k: v for k, v in merged_data.items() if k != "transactions"}
    items = list(scalars.items())
    half = (len(items) + 1) // 2
    left, right = st.columns(2)
    for col, chunk in ((left, items[:half]), (right, items[half:])):
        with col:
            for k, v in chunk:
                st.write(f"**{k}**: {v}")


def render_transactions(merged_data):
    # render the transaction table as an actual table, not a JSON blob
    txns = merged_data.get("transactions") or []
    if not txns:
        st.caption("No transactions extracted.")
        return
    st.dataframe(txns, use_container_width=True)
    st.caption(f"{len(txns)} transactions")


def render_validation(validation_result):
    if not validation_result:
        st.caption("No validation result.")
        return
    if validation_result["is_valid"]:
        st.success("All checks passed.")
    else:
        st.error(f"{len(validation_result['errors'])} check(s) failed.")
        st.dataframe(validation_result["errors"], use_container_width=True)


def render_reflection(reflection_result):
    # only present when validation failed and the reflection agent ran
    if not reflection_result:
        st.caption("No reflection (validation passed).")
        return
    st.write(f"**Mistake:** {reflection_result.get('mistake_description')}")
    st.write(f"**Correction rule:** {reflection_result.get('correction_rule')}")
    st.write(f"**Confidence:** {reflection_result.get('confidence')}")


def render_concurrency(telemetry):
    # use the per-agent start/end timestamps to prove the 3 agents overlapped
    if not telemetry:
        st.caption("No telemetry.")
        return
    extraction = [c for c in telemetry["calls"] if c["agent_name"] in ("identity", "account", "transactions")]
    rows = [{"agent": c["agent_name"], "start": c["start_time"], "end": c["end_time"]} for c in extraction]
    st.dataframe(rows, use_container_width=True)

    # crude overlap check: if the latest start is before the earliest end, they overlapped
    times = [(c["start_time"], c["end_time"]) for c in extraction if c["start_time"] and c["end_time"]]
    if len(times) >= 2:
        starts = [datetime.fromisoformat(s) for s, _ in times]
        ends = [datetime.fromisoformat(e) for _, e in times]
        if max(starts) < min(ends):
            st.success("Agents overlapped in time -> they ran concurrently.")
        else:
            st.warning("No overlap detected -> they may have run sequentially.")


def render_telemetry(telemetry):
    if not telemetry:
        st.caption("No telemetry.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Total cost ($)", round(telemetry["total_cost"], 6))
    c2.metric("Input tokens", telemetry["total_input_tokens"])
    c3.metric("Output tokens", telemetry["total_output_tokens"])
    rows = [
        {"agent": agent, "input_tokens": d["input_tokens"], "output_tokens": d["output_tokens"], "cost": round(d["cost"], 6)}
        for agent, d in telemetry["by_agent"].items()
    ]
    st.dataframe(rows, use_container_width=True)


def render_prompt_versions(prompt_versions):
    if not prompt_versions:
        st.caption("No prompt versions recorded.")
        return
    st.json(prompt_versions)


def render_human_review(result):
    #Human confirms or overrides what the automated system decided
    st.subheader("Human review")

    approve = st.button("Approve", type="primary")
    reject_note = st.text_area("If rejecting, describe what was actually wrong:")
    reject = st.button("Reject")

    if approve:
        path = save_approved_result(result)
        # if this run auto-produced a correction, a human just confirmed it
        reflection = result.get("reflection_result")
        if reflection and reflection.get("correction_rule"):
            mark_correction_confirmed(EPISODIC_FILE, result.get("source"), reflection.get("correction_rule"))
        st.success(f"Approved. Saved to {path}")

    if reject:
        if reject_note.strip():
            # log the human-caught problem, tagged as human so it isn't confused
            # with something the automated validator found
            add_episodic_entry(
                EPISODIC_FILE,
                result.get("source"),
                reject_note.strip(),
                reject_note.strip(),
                1.0,
                caught_by="human",
                human_confirmed=True,
            )
            check_for_promotion(EPISODIC_FILE, SEMANTIC_FILE, threshold=2)
            st.warning("Logged your correction to memory (tagged as human).")
        else:
            st.info("Please describe what was wrong before rejecting.")


def render_memory_view():
    # letting user see what the system has learned so far
    
    st.header("Memory")

    semantic = load_semantic_memory(SEMANTIC_FILE)
    st.subheader(f"Semantic rules (promoted / confirmed) - {len(semantic)}")
    if semantic:
        st.dataframe(semantic, use_container_width=True)
    else:
        st.caption("No promoted rules yet.")

    episodic = load_episodic_memory(EPISODIC_FILE)
    st.subheader(f"Episodic log (every correction) - {len(episodic)}")
    if episodic:
        st.dataframe(episodic, use_container_width=True)
    else:
        st.caption("No episodic entries yet.")


# sidebar: pick a document, name the bank, run 
with st.sidebar:
    st.header("Run a document")

    # list the PDFs inside our allowed folder
    pdf_files = sorted(p.name for p in STATEMENTS_DIR.glob("*.pdf"))

    if not pdf_files:
        st.warning(f"No PDFs found in {STATEMENTS_DIR}. place a statement there first.")
        selected_pdf = None
    else:
        selected_pdf = st.selectbox("Statement PDF", pdf_files)

    # the bank name becomes the memory 'source'. run_pipeline normalizes it.
    source = st.text_input("Bank / source", placeholder="e.g. Chase, Wells Fargo, HSBC")

    run_clicked = st.button("Run", type="primary", disabled=not (selected_pdf and source))


#run the pipeline
if run_clicked:
    pdf_path = str(STATEMENTS_DIR / selected_pdf)

    # st.status gives us a live, expandable box. we consume the generator and
    # print each stage as it arrives, then keep the final event in session_state.
    with st.status("Running pipeline...", expanded=True) as status:
        for event in run_pipeline(pdf_path, STATEMENTS_DIR, source):
            stage = event["stage"]
            st.write(f"stage: {stage}")

            if stage == "error":
                status.update(label=f"Failed: {event['error']}", state="error")
                st.session_state["result"] = event
            elif stage == "complete":
                status.update(label="Done", state="complete")
                st.session_state["result"] = event


#main area it shows the final result after the pipeline finishes. 
result = st.session_state["result"]

if result is None:
    st.info("Pick a statement and a bank in the sidebar, then hit Run.")
elif result.get("error"):
    st.error(result["error"])
else:
    md = result["merged_data"]

    st.caption(f"source: {result.get('source')}  |  run_id: {result.get('run_id')}")

    st.subheader("Extracted fields")
    render_merged_fields(md)

    st.subheader("Transactions")
    render_transactions(md)

    st.subheader("Validation")
    render_validation(result.get("validation_result"))

    st.subheader("Reflection")
    render_reflection(result.get("reflection_result"))

    with st.expander("Concurrency evidence (did the 3 agents overlap?)"):
        render_concurrency(result.get("telemetry"))

    with st.expander("Telemetry (cost & tokens)"):
        render_telemetry(result.get("telemetry"))

    with st.expander("Prompt versions used"):
        render_prompt_versions(result.get("prompt_versions"))

    render_human_review(result)


st.divider()
render_memory_view()
