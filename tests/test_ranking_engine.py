import json

from ranking_engine import WEIGHTS, load_candidates


def test_weights_sum_to_100():
    total_weights = sum(WEIGHTS.values())
    assert total_weights == 100


def test_load_candidates_deduplication(tmp_path):
    nlp_dir = tmp_path / "nlp"
    nlp_dir.mkdir()

    cand1 = {
        "personal_info": {"name": "Alice Smith"},
        "domain": "Software Engineering",
    }
    cand2 = {
        "personal_info": {"name": "Alice Smith"},
        "domain": "Software Engineering",
    }
    cand3 = {
        "personal_info": {"name": "Bob Jones"},
        "domain": "Data Science",
    }

    (nlp_dir / "c1_nlp.json").write_text(json.dumps(cand1), encoding="utf-8")
    (nlp_dir / "c2_nlp.json").write_text(json.dumps(cand2), encoding="utf-8")
    (nlp_dir / "c3_nlp.json").write_text(json.dumps(cand3), encoding="utf-8")

    loaded = load_candidates(nlp_dir)
    assert len(loaded) == 2
    names = [c["personal_info"]["name"] for c in loaded]
    assert "Alice Smith" in names
    assert "Bob Jones" in names
