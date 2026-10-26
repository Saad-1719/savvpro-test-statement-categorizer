import shutil
from pathlib import Path

import pytest

from app.rules.loader import RULES_DIR, RulesError, load_rules


@pytest.fixture
def rules_dir(tmp_path: Path) -> Path:
    for f in RULES_DIR.glob("*.yaml"):
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text() + text)


def test_shipped_rules_load() -> None:
    rules = load_rules()
    assert rules.rule_count > 50
    assert "Fuel" in rules.categories


def test_unknown_category_fails(rules_dir: Path) -> None:
    append(
        rules_dir / "merchants.yaml", "\n- {id: m.x, match: prefix, pattern: X, category: Snacks}\n"
    )
    with pytest.raises(RulesError, match="unknown category"):
        load_rules(rules_dir)


def test_duplicate_id_fails(rules_dir: Path) -> None:
    append(
        rules_dir / "keywords.yaml",
        "\n- {id: merchant.shell, match: contains, pattern: X, category: Fuel}\n",
    )
    with pytest.raises(RulesError, match="duplicate"):
        load_rules(rules_dir)


def test_bad_yaml_fails(rules_dir: Path) -> None:
    (rules_dir / "types.yaml").write_text("- id: [unclosed\n")
    with pytest.raises(RulesError):
        load_rules(rules_dir)


def test_bad_regex_fails(rules_dir: Path) -> None:
    append(
        rules_dir / "types.yaml",
        '\n- {id: t.bad, match: regex, pattern: "(", category: Transfer}\n',
    )
    with pytest.raises(RulesError, match="bad regex"):
        load_rules(rules_dir)


def test_review_rule_needs_reason(rules_dir: Path) -> None:
    append(
        rules_dir / "merchants.yaml", "\n- {id: m.r, match: prefix, pattern: X, action: review}\n"
    )
    with pytest.raises(RulesError, match="reason"):
        load_rules(rules_dir)


def test_categorize_rule_needs_category(rules_dir: Path) -> None:
    append(rules_dir / "merchants.yaml", "\n- {id: m.c, match: prefix, pattern: X}\n")
    with pytest.raises(RulesError, match="category"):
        load_rules(rules_dir)


def test_rules_are_sorted_most_specific_first() -> None:
    merchants = load_rules().merchants
    ids = [r.id for r in merchants]
    assert ids.index("merchant.platform_tips") < ids.index("merchant.platform_payout")
    assert ids.index("merchant.uber_eats") < ids.index("merchant.uber_ambiguous")
    assert ids.index("merchant.exxonmobil") < ids.index("merchant.exxon")


def test_tax_form_needs_a_name(rules_dir: Path) -> None:
    (rules_dir / "tax_form.yaml").write_text("note: no name here\n")
    with pytest.raises(RulesError, match="tax_form"):
        load_rules(rules_dir)
