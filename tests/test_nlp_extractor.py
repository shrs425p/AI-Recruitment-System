from nlp_extractor import build_prompt


def test_build_prompt_embeds_resume_text():
    sample_text = "John Doe, Senior Software Engineer with 8 years of Python experience."
    prompt = build_prompt(sample_text)

    assert sample_text in prompt
    assert "personal_info" in prompt
    assert "skills" in prompt
    assert "work_experience" in prompt
