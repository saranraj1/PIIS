"""Unit tests for telecom-aware tokenizer."""

from __future__ import annotations

from piis.retrieval.tokenizer import TelecomTokenizer


def test_telecom_tokenizer_preserves_alarm_identifiers():
    tok = TelecomTokenizer()
    text = "Active alarm ALM-RAN-VSWR-HIGH on antenna port 1 with return loss collapse."
    tokens = tok.tokenize(text)

    assert "ALM-RAN-VSWR-HIGH" in tokens
    assert "antenna" in tokens
    assert "port" in tokens
    assert "with" not in tokens  # Stopword removed


def test_telecom_tokenizer_preserves_hex_and_interfaces():
    tok = TelecomTokenizer()
    text = "Error code 0x80040111 triggered on N4 interface between SMF and UPF."
    tokens = tok.tokenize(text)

    assert "0x80040111" in tokens
    assert "n4" in [t.lower() for t in tokens]
    assert "smf" in [t.lower() for t in tokens]
    assert "upf" in [t.lower() for t in tokens]


def test_telecom_tokenizer_preserves_acronyms_and_kpis():
    tok = TelecomTokenizer()
    text = "gNodeB reported RSRP of -75 dBm, DL_BLER of 0.05, and UL_MCS drop to 9."
    tokens = tok.tokenize(text)

    assert any(t.lower() == "gnodeb" for t in tokens)
    assert any("rsrp" in t.lower() for t in tokens)
    assert any("bler" in t.lower() for t in tokens)
    assert any("mcs" in t.lower() for t in tokens)
