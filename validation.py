from datetime import datetime


def check_required_fields(merged_data: dict) -> list:
    """
    Checks that keys of identity/account fields are present and non-empty.
    Returns a list of error dicts (empty list if everything's fine).
    """
    errors = []
    required_fields = [
        "customer_name",
        "mailing_address",
        "account_number",
        "statement_period_start",
        "statement_period_end",
    ]

    for field in required_fields:
        value = merged_data.get(field)
        if value is None or value == "":
            errors.append({
                "check": "required_fields",
                "field": field,
                "message": f"{field} is missing"
            })

    return errors

#opening_balance + total_paid_in − total_paid_out == closing_balance
def check_final_balance(merged_data: dict) -> list:
    """
    Checks that the final balance is correct.
    Returns a list of error dicts (empty list if everything's fine).
    """
    errors = []
    opening_balance = merged_data.get("opening_balance")
    closing_balance = merged_data.get("closing_balance")
    if merged_data.get("transactions") is None:
        errors.append({
            "check": "final_balance",
            "message": "Transactions data is missing"
        })
        return errors
    total_paid_in = sum(t["paid_in"] for t in merged_data.get("transactions"))
    total_paid_out = sum(t["paid_out"] for t in merged_data.get("transactions"))

    if opening_balance is not None and closing_balance is not None:
        if abs(opening_balance + total_paid_in - total_paid_out - closing_balance) > 0.01:  # Allowing a small tolerance for floating point arithmetic
            errors.append({
                "check": "final_balance",
                "message": f"Final balance check failed: opening_balance ({opening_balance}) + total_paid_in ({total_paid_in}) - total_paid_out ({total_paid_out}) != closing_balance ({closing_balance})"
            })
    return errors  

def check_row_by_row_balance(merged_data: dict) -> list:
    """
    Checks that each transaction's balance is correct.
    Returns a list of error dicts (empty list if everything's fine).
    """
    errors = []
    running_balance = merged_data.get("opening_balance", 0)
    if merged_data.get("transactions") is None:
        errors.append({
            "check": "row_by_row_balance",
            "message": "Transactions data is missing"
        })
        return errors
    transactions = merged_data.get("transactions", [])
    for index, transaction in enumerate(transactions):
        running_balance = running_balance + transaction.get("paid_in", 0) - transaction.get("paid_out", 0)
        if abs(running_balance - transaction.get("balance", 0)) > 0.01:  # Allowing a small tolerance for floating point arithmetic
            errors.append({
                "check": "row_by_row_balance",
                "transaction_index": index,
                "message": f"Row {index} balance check failed: running_balance ({running_balance}) != transaction balance ({transaction.get('balance', 0)})"
            })

    return errors



def check_date_range(merged_data: dict) -> list:
    """
    Checks that the statement period is valid.
    Returns a list of error dicts (empty list if everything's fine).
    """
    errors = []
    start_date = merged_data.get("statement_period_start")
    end_date = merged_data.get("statement_period_end")

    if start_date is None or end_date is None:
        errors.append({
            "check": "date_range",
            "message": "Statement period start or end date is missing"
        })
        return errors
    
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        errors.append({
            "check": "date_range",
            "message": f"Invalid date format: {e}"
        })
        return errors
    
    if merged_data.get("transactions") is None:
        errors.append({
            "check": "date_range",
            "message": "Transactions data is missing"
        })
        return errors
    transactions = merged_data.get("transactions", [])

    for index, transaction in enumerate(transactions):
        transaction_date = transaction.get("date")
        if transaction_date is None:
            errors.append({
                "check": "date_range",
                "transaction_index": index,
                "message": f"Transaction date is missing for row {index}"
            })
            continue
        try:
            transaction_date_obj = datetime.strptime(transaction_date, "%Y-%m-%d")
        except ValueError as e:
            errors.append({
                "check": "date_range",
                "transaction_index": index,
                "message": f"Invalid transaction date format for row {index}: {e}"
            })
            continue
        if not (start_date_obj <= transaction_date_obj <= end_date_obj):
            errors.append({
                "check": "date_range",
                "transaction_index": index,
                "message": f"Transaction date {transaction_date} for row {index} is outside the statement period ({start_date} to {end_date})"
            })
    return errors  

def validate_merged_data(merged_data: dict) -> dict:
    """
    Validates the merged data by running all checks.
    Returns a list of error dicts (empty list if everything's fine).
    """
    all_errors = []
    all_errors += check_required_fields(merged_data)
    all_errors += check_final_balance(merged_data)
    all_errors += check_row_by_row_balance(merged_data)
    all_errors += check_date_range(merged_data)
    return {
        "is_valid": len(all_errors) == 0,
        "errors": all_errors
    }
      