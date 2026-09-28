"""Claim → evidence → strength → controls auditing. Fixtures are synthetic."""
from sciguard.induction import (audit_claims, claim_preparse, claim_strength, format_audit,
                                is_negative, strongest_strength_word)


def test_strength_ladder_from_the_verb():
    assert claim_strength("These data demonstrate turnover.") == "strong"
    assert claim_strength("These data suggest turnover.") == "moderate"
    assert claim_strength("The result may hint at turnover.") == "weak"


def test_explicit_annotation_wins():
    assert claim_strength("These data demonstrate turnover.", explicit="weak") == "weak"


def test_an_unmarked_claim_is_not_charitably_downgraded():
    # Overclaim is the failure mode being guarded, so no verb means moderate, never weak.
    assert claim_strength("The variant turned over the substrate.") == "moderate"


def test_a_claim_with_no_evidence_is_flagged():
    a = audit_claims([{"text": "The variant is active."}])
    assert any(f["type"] == "no_evidence" for f in a["flags"])
    assert a["ok"] is False


def test_a_strong_claim_must_list_controls():
    a = audit_claims([{"text": "We demonstrate turnover.", "evidence": ["assay-1"]}])
    assert any(f["type"] == "overclaim_no_controls" for f in a["flags"])


def test_a_strong_claim_may_not_rest_on_a_tripped_sensor():
    a = audit_claims([{"text": "We demonstrate turnover.", "evidence": ["assay-1"],
                       "controls": ["no-enzyme", "no-cofactor"]}],
                     tripped_sensors={"assay-1"})
    assert any(f["type"] == "overclaim_tripped_sensor" for f in a["flags"])


def test_an_absence_claim_must_be_lod_bounded():
    bare = audit_claims([{"text": "No product was detected.", "evidence": ["lcms-3"]}])
    bounded = audit_claims([{"text": "No product was detected.", "evidence": ["lcms-3"],
                             "lod_bounded": True}])
    assert any(f["type"] == "negative_not_lod_bounded" for f in bare["flags"])
    assert not any(f["type"] == "negative_not_lod_bounded" for f in bounded["flags"])


def test_is_negative_detects_absence_language():
    assert is_negative({"text": "the variant was inactive"}) is True
    assert is_negative({"text": "the variant was active"}) is False


def test_a_headline_claim_must_be_retrieval_checked():
    a = audit_claims([{"text": "This is a new reaction type.", "evidence": ["x"], "headline": True}])
    assert any(f["type"] == "headline_not_retrieval_checked" for f in a["flags"])


def test_a_well_formed_map_passes():
    a = audit_claims([{"text": "The data suggest turnover.", "evidence": ["assay-1"]}])
    assert a["ok"] is True and a["n_claims"] == 1 and a["n_strong"] == 0


def test_claim_preparse_splits_sentences_and_finds_citation_tokens():
    para = ("The variant demonstrates turnover (Figure 2; p < 0.01). "
            "We confirm the product identity (Table S3; m/z 412.2, n = 3). "
            "The mechanism may be concerted.")
    recs = claim_preparse(para)
    assert len(recs) == 3
    assert recs[0]["strength_word"] == "demonstrate"
    assert recs[0]["has_evidence"] is True
    assert recs[2]["has_evidence"] is False       # no cite token in the last sentence


def test_data_ids_are_matched_never_fabricated():
    recs = claim_preparse("K72A shows clear turnover.", data_ids=("K72A", "D145N"))
    assert "K72A" in recs[0]["cites"]
    assert "D145N" not in recs[0]["cites"]


def test_strongest_strength_word_picks_the_strongest_cue():
    assert strongest_strength_word("this may suggest a role") == "suggest"


def test_format_audit_is_printable():
    assert "claim" in format_audit(audit_claims([{"text": "x"}])).lower()
