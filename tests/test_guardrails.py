import pytest
from src.guardrails import screen_query
from src.guardrails.output_validator import validate_response

def test_pii_detection():
    # PAN
    res = screen_query("My PAN is ABCDE1234F")
    assert res['allowed'] == False
    assert "personal information" in res['refusal_response']
    
    # Aadhaar
    res = screen_query("Check this Aadhaar 1234 5678 9012")
    assert res['allowed'] == False
    
    # Phone
    res = screen_query("Call me at +91 9876543210")
    assert res['allowed'] == False

def test_intent_advisory():
    res = screen_query("Should I invest in HDFC Mid Cap?")
    assert res['allowed'] == False
    assert "cannot provide investment advice" in res['refusal_response']

def test_intent_performance():
    res = screen_query("Which fund gave better returns?")
    assert res['allowed'] == False
    assert "cannot compare fund performance" in res['refusal_response']

def test_intent_out_of_scope():
    res = screen_query("Tell me about Axis Bluechip Fund")
    assert res['allowed'] == False
    assert "cover only HDFC Mutual Fund schemes" in res['refusal_response']

def test_intent_factual():
    res = screen_query("What is the expense ratio of HDFC Large Cap?")
    assert res['allowed'] == True

def test_output_validation_valid():
    # Valid
    valid_resp = {
        'answer': 'The expense ratio is 1.04%. For more info, check the link. Last updated from sources: 04 Jul 2026',
        'citation_url': 'https://groww.in/link',
        'last_updated': '04 Jul 2026'
    }
    val = validate_response(valid_resp)
    assert val['valid'] == True

def test_output_validation_invalid_advisory():
    # Invalid (Advisory leak)
    invalid_resp = {
        'answer': 'I recommend you invest in this fund. It is a good investment.',
        'citation_url': 'https://groww.in/link',
        'last_updated': '04 Jul 2026'
    }
    val = validate_response(invalid_resp)
    assert val['valid'] == False
    assert val['corrected_response']['citation_url'] == ""
