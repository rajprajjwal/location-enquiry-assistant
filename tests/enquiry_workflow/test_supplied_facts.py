from copilot.response_drafting.supplied_facts import extract_supplied_facts, repeated_fact_fields


def values(enquiry):
    return {fact["field"]: fact["value"] for fact in extract_supplied_facts(enquiry)}


def test_customer_history_is_used_and_assistant_claims_are_excluded():
    enquiry = {
        "query": "Please proceed.",
        "history": [
            {"role": "user", "text": "We send 24,000 requests per month."},
            {"role": "assistant", "text": "You use Mapbox with 100,000 requests per year."},
        ],
    }
    assert values(enquiry) == {"workload": 24000, "workload_period": "month"}


def test_explicit_current_workload_overrides_earlier_value():
    result = values({
        "query": "Actually we send 60,000 requests per month.",
        "history": [{"role": "user", "text": "We send 20,000 requests per year."}],
    })
    assert result == {"workload": 60000, "workload_period": "month"}


def test_missing_header_is_a_supplied_false_value():
    facts = extract_supplied_facts({"query": "We do not send a User-Agent."})
    assert facts[0]["value"] is False
    assert repeated_fact_fields({"facts": ["missing_user_agent"]}, facts) == ["user_agent_present"]


def test_bound_and_error_status_do_not_supply_exact_count_or_response_message():
    result = values({"query": "We use more than 8 waypoints. The request returns 422."})
    assert result == {"waypoint_lower_bound_exclusive": 8, "http_status": ["422"]}


def test_mixed_question_with_an_unknown_fact_is_retained():
    facts = extract_supplied_facts({"query": "We send 42,000 calls a month."})
    assert repeated_fact_fields({"facts": ["duration_of_usage", "request_example"]}, facts) == []
    assert repeated_fact_fields({"facts": ["duration_of_usage"]}, facts) == ["workload_period"]


def test_unspecified_coordinates_and_credential_rotation_date_stay_unknown():
    result = values({"query": "Some GPS coordinates fail after we rotated OAuth credentials."})
    assert "coordinates" not in result
    assert "oauth_credential_rotation_date" not in result
