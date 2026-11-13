"""Unit tests for PIIS prediction-time feature extraction pipeline."""

from piis.classification.features import IncidentFeatureExtractor
from piis.normalization.contracts import PredictionTimeFeatureContract


def test_feature_extractor_quarantine_enforcement():
    leaking_record = {
        "incident_id": "INC-TEST-001",
        "title": "Degraded radio link",
        "description": "High BLER on sector 101",
        "network_domain": "RAN",
        "affected_subscribers": 50,
        "network_element_ids": ["GNB-101"],
        "resolved_at": "2026-03-01T12:00:00Z",
        "resolution_summary": "Replaced antenna jumper cable.",
        "root_cause_confirmed": True,
    }

    extractor = IncidentFeatureExtractor(max_tfidf_features=100)
    df_feat, targets = extractor.prepare_dataframe([leaking_record], strict_quarantine=True)

    # Leaking fields must be completely absent from df_feat columns
    assert "resolution_summary" not in df_feat.columns
    assert "resolved_at" not in df_feat.columns
    assert "root_cause_confirmed" not in df_feat.columns

    # Permitted triage fields must be present
    assert "text_content" in df_feat.columns
    assert "network_domain" in df_feat.columns
    assert "log_subscribers" in df_feat.columns
    assert df_feat.iloc[0]["network_domain"] == "RAN"


def test_feature_extractor_fit_transform():
    records = [
        {
            "incident_id": "INC-01",
            "title": "RAN degradation",
            "description": "Block errors elevated",
            "network_domain": "RAN",
            "affected_subscribers": 100,
            "network_element_ids": ["GNB-1"],
            "fault_category": "ran_signal_degradation",
        },
        {
            "incident_id": "INC-02",
            "title": "Core authentication timeout",
            "description": "AUSF SBI failure",
            "network_domain": "5G_CORE",
            "affected_subscribers": 500,
            "network_element_ids": ["AUSF-1"],
            "fault_category": "subscriber_authentication_failure",
        },
    ]

    extractor = IncidentFeatureExtractor(max_tfidf_features=50)
    df_feat, targets = extractor.prepare_dataframe(records)

    matrix = extractor.fit_transform(df_feat)
    assert matrix.shape[0] == 2
    assert matrix.shape[1] > 2

    feature_names = extractor.get_feature_names()
    assert len(feature_names) == matrix.shape[1]
    contract = PredictionTimeFeatureContract()
    contract.validate_feature_vector(feature_names)
