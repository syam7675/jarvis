"""Local catalog tests; no remote skill install or model inference."""

from personal.skills import catalog, find, main


def test_catalog_has_real_instruction_files():
    skills = catalog()
    assert len(skills) >= 5
    assert all(skill.path.is_file() and skill.instructions for skill in skills)
    assert len({skill.name for skill in skills}) == len(skills)


def test_find_matches_keywords_and_rejects_unknown_topics():
    assert find("PHONE")[0].name == "call-preparation"
    assert find("python")[0].name == "implementation-advisor"
    assert not find("qzxvnonexistent")
    assert len(find("")) == len(catalog())


def test_cli_returns_only_matching_skills(capsys):
    assert main(["phone"]) == 0
    output = capsys.readouterr().out
    assert "call-preparation" in output
    assert "implementation-advisor" not in output
