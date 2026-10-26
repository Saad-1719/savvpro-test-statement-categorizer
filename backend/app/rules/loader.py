"""Load the YAML rule files into validated, pre-sorted rule sets.

Fails fast on bad YAML, a duplicate rule ID or an unknown category, so a broken
rule never reaches the brain.
"""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models import Category, Rule

RULES_DIR = Path(__file__).parent

_MATCH_RANK = {"exact": 0, "prefix": 1, "regex": 2, "contains": 3}


class RulesError(ValueError):
    """A rule file is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class RuleSet:
    categories: dict[str, Category]
    types: list[Rule]
    merchants: list[Rule]
    keywords: list[Rule]
    deny_list: list[str]
    by_id: dict[str, Rule] = field(default_factory=dict)
    tax_form_name: str = ""
    tax_form_note: str = ""

    @property
    def rule_count(self) -> int:
        return len(self.types) + len(self.merchants) + len(self.keywords) + len(self.deny_list)


def _read_yaml(path: Path) -> list:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RulesError(f"{path.name}: {exc}") from exc
    if not isinstance(data, list):
        raise RulesError(f"{path.name}: expected a list at the top level")
    return data


def most_specific_first(rules: list[Rule]) -> list[Rule]:
    """Sort a layer's rules so the first match is the most specific one.

    1. Higher `priority` first (used rarely, e.g. tips before payouts).
    2. Then by match type: exact, prefix, regex, contains.
    3. Then the longer pattern first, so "UBER *EATS" beats "UBER".
    Rules that tie keep their order from the YAML file (Python's sort is stable).
    """

    def sort_key(rule: Rule) -> tuple[int, int, int]:
        return (-rule.priority, _MATCH_RANK[rule.match], -len(rule.pattern))

    return sorted(rules, key=sort_key)


def _load_layer(path: Path, layer: str, categories: dict[str, Category]) -> list[Rule]:
    rules: list[Rule] = []
    for position, raw in enumerate(_read_yaml(path)):
        if not isinstance(raw, dict):
            raise RulesError(f"{path.name}: entry {position} is not a mapping")
        try:
            rule = Rule(layer=layer, **raw)
        except (ValidationError, TypeError) as exc:
            raise RulesError(f"{path.name}: entry {position}: {exc}") from exc
        if rule.category and rule.category not in categories:
            raise RulesError(f"{path.name}: rule {rule.id} has unknown category {rule.category!r}")
        rules.append(rule)
    return most_specific_first(rules)


def load_rules(rules_dir: Path = RULES_DIR) -> RuleSet:
    categories: dict[str, Category] = {}
    for raw in _read_yaml(rules_dir / "categories.yaml"):
        try:
            category = Category(**raw)
        except (ValidationError, TypeError) as exc:
            raise RulesError(f"categories.yaml: {exc}") from exc
        categories[category.name] = category

    types = _load_layer(rules_dir / "types.yaml", "type", categories)
    merchants = _load_layer(rules_dir / "merchants.yaml", "merchant", categories)
    keywords = _load_layer(rules_dir / "keywords.yaml", "keyword", categories)

    by_id: dict[str, Rule] = {}
    for rule in [*types, *merchants, *keywords]:
        if rule.id in by_id:
            raise RulesError(f"duplicate rule id {rule.id!r}")
        by_id[rule.id] = rule

    deny_list = [str(item).strip().upper() for item in _read_yaml(rules_dir / "deny_list.yaml")]
    try:
        tax_form = yaml.safe_load((rules_dir / "tax_form.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RulesError(f"tax_form.yaml: {exc}") from exc
    if not isinstance(tax_form, dict) or not tax_form.get("name"):
        raise RulesError("tax_form.yaml: needs at least a `name`")

    return RuleSet(
        categories=categories,
        types=types,
        merchants=merchants,
        keywords=keywords,
        deny_list=deny_list,
        by_id=by_id,
        tax_form_name=tax_form["name"],
        tax_form_note=tax_form.get("note", ""),
    )


@cache
def default_rules() -> RuleSet:
    return load_rules()
