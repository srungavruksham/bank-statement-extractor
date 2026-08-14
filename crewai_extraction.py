import threading
import uuid
from datetime import datetime
from crewai import Agent, Task, Crew, Process

from prompts import registry
from utils import parse_json_response
from telemetry.tracker import record_call

import json



def create_identity_agent(llm):
    return Agent(
        role = "you're a Bank statement parser. Your task is to extract the identity information from the bank statement.",
        goal = """Extract Structured data from the bank statement while maintaining accuracy and consistency. 
                The extracted data should be in a structured format, such as JSON, and should include all relevant identity information.""",
        backstory = """You are a highly skilled and experienced bank statement parser with a deep understanding of financial documents.
                You have a keen eye for detail and are able to extract relevant information from complex documents with ease.
                Your expertise in parsing bank statements allows you to identify and extract identity information accurately and efficiently.""",
        llm = llm,
        verbose = True        
    )

def create_account_agent(llm):
    return Agent(
        role = "you're a Bank statement parser. Your task is to extract the account information from the bank statement.",
        goal = "Extract Structured data from the bank statement while maintaining accuracy and consistency.",
        backstory = """You are a highly skilled and experienced bank statement parser with a deep understanding of financial documents.
                You have a keen eye for detail and are able to extract relevant information from complex documents with ease.
                Your expertise in parsing bank statements allows you to identify and extract account information accurately and efficiently.""",
        llm = llm,
        verbose = True        
    )

def create_transactions_agent(llm):
    return Agent(
        role = "you're a Bank statement parser. Your task is to extract the transactions information from the bank statement.",
        goal = "Extract Structured data from the bank statement while maintaining accuracy and consistency.",
        backstory = """You are a highly skilled and experienced bank statement parser with a deep understanding of financial documents.
                You have a keen eye for detail and are able to extract relevant information from complex documents with ease.
                Your expertise in parsing bank statements allows you to identify and extract transactions information accurately and efficiently.""",
        llm = llm,
        verbose = True        
    )

def create_merge_agent(llm):
    return Agent(
        role = "you're a Bank statement parser. Your task is to merge the extracted identity and account into a single structured data format.",
        goal = "Merge the extracted identity and account information into a single structured data format while maintaining accuracy and consistency.",
        backstory = """You are a highly skilled and experienced bank statement parser with a deep understanding of financial documents.
                You have a keen eye for detail and are able to extract relevant information from complex documents with ease.
                Your expertise in parsing bank statements allows you to identify and merge identity and account information accurately and efficiently.""",
        llm = llm,
        verbose = True        
    )

def create_reflection_agent(llm):
    return Agent(
        role = "you're a learning reflector or learning analyst",
        goal = "Analyse validation feedback and produce a correction rule",
        backstory = "Agent that learns from errors and improves extraction patterns over time",
        llm = llm,
        verbose = True
    )    


def create_identity_task(agent,document_text,memory_context=""):
    return Task(
        description = registry.get_prompt("identity", document_text=document_text, memory_context=memory_context),
        agent = agent,
        expected_output = "Structured JSON data containing identity information extracted from the bank statement."
    )

def create_account_task(agent,document_text,memory_context=""):
    return Task(
        description = registry.get_prompt("account", document_text=document_text, memory_context=memory_context),
        agent = agent,
        expected_output = "Structured JSON data containing account information extracted from the bank statement."
    )
def create_transactions_task(agent,document_text,memory_context=""):
    return Task(
        description = registry.get_prompt("transactions", document_text=document_text, memory_context=memory_context),
        agent = agent,
        expected_output = "Structured JSON data containing transactions information extracted from the bank statement."
    )

def create_merge_task(agent,identity_json,account_json):
    return Task(
        description = registry.get_prompt("merge", identity_json=identity_json, account_json=account_json),
        agent = agent,
        expected_output = "Structured JSON data containing merged identity and account information extracted from the bank statement."
    )
def create_reflection_task(agent,document_text,validation_feedback):
    return Task(
        description = registry.get_prompt("reflection", document_text=document_text, validation_feedback=validation_feedback),
        agent = agent,
        expected_output = "Provide correction rules based on validation feedback."
    )

def run_agent(agent,task,telemetry_file, run_id, agent_name, model):
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    start_time = datetime.now().isoformat()   # captured before the LLM call starts
    result = crew.kickoff()
    end_time = datetime.now().isoformat()      # captured after it returns
    record_call(
        telemetry_file, run_id, agent_name, model,
        input_tokens=result.token_usage.prompt_tokens,
        output_tokens=result.token_usage.completion_tokens,
        start_time=start_time,
        end_time=end_time
    )  # Record the call with telemetry
    return parse_json_response(str(result))

def run_agent_and_store(name, agent, task, results, llm, run_id, telemetry_file):
    try:
        results[name] = run_agent(agent, task, agent_name=name, model=llm, telemetry_file=telemetry_file, run_id=run_id)
    except Exception as e:
        # store None so the key exists, but also keep the real error message
        results[name] = None
        results[f"{name}_error"] = str(e)

def extract_parallel(identity_agent, account_agent, transactions_agent, identity_task, account_task, transactions_task, llm, run_id, telemetry_file):
    jobs = [
        ("identity", identity_agent, identity_task),       #tuples with Label(name), Agent, Task
        ("account", account_agent, account_task),
        ("transactions", transactions_agent, transactions_task)
    ]

    results = {}
    threads = []

    for name, agent, task in jobs:
        t = threading.Thread(target=run_agent_and_store, args=(name, agent, task, results,llm, run_id, telemetry_file))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # if any thread failed, raise a clear error instead of a KeyError later
    for name, _, _ in jobs:
        if results.get(name) is None:
            err = results.get(f"{name}_error", "unknown error")
            raise RuntimeError(f"{name} agent failed: {err}")

    return results

def extract_and_merge(llm,document_text,run_id,telemetry_file,memory_context=""):
    # Create agents for identity, account, and transactions
    identity_agent = create_identity_agent(llm)
    account_agent = create_account_agent(llm)
    transactions_agent = create_transactions_agent(llm)
    
    # Create tasks for each agent with the provided document text and any learned memory
    identity_task = create_identity_task(identity_agent, document_text, memory_context)
    account_task = create_account_task(account_agent, document_text, memory_context)
    transactions_task = create_transactions_task(transactions_agent, document_text, memory_context)

    # Run the agents in parallel to extract identity, account, and transactions data
    extracted_results = extract_parallel(identity_agent, account_agent, transactions_agent, identity_task, account_task, transactions_task, llm, run_id, telemetry_file)

    # Merge the extracted identity and account data into a single structured format
    identity_json = json.dumps(extracted_results["identity"])
    account_json = json.dumps(extracted_results["account"])

    merge_agent = create_merge_agent(llm)
    merge_task = create_merge_task(merge_agent, identity_json, account_json)
    merged_result = run_agent(merge_agent, merge_task, agent_name="merge_agent", model=llm, run_id=run_id, telemetry_file=telemetry_file)

    #Splice in the transactions array using plain code, since we don't allow merge agent to handle transactions
    final_data = dict(merged_result)
    final_data.update(extracted_results["transactions"])

    return final_data



     
    
    





