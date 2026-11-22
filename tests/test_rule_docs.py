from app import rule_docs


def test_generated_rule_files_are_up_to_date():
    stale = [p.name for p, text in rule_docs.render_all().items() if not p.exists() or p.read_text() != text]
    assert not stale, f"Run `python -m app.rule_docs` to refresh: {stale}"


def test_every_rule_id_is_unique_and_belongs_to_a_documented_family():
    rules = rule_docs.collect()
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == len(set(ids))
    known = {prefix for prefix, _, _ in rule_docs.FAMILIES}
    assert {r["family"] for r in rules} <= known
