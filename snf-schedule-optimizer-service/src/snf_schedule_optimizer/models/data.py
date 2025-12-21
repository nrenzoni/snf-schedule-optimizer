from dataclasses import dataclass


@dataclass(frozen=True)
class DifferentialRuleData:
    """Raw data representation of a differential rule from the DB."""

    rule_id: str
    org_id: str
    description: str
    amount: float
    priority: int
    applicable_job_titles: list[str] | None
    contract_id: str | None


@dataclass(frozen=True)
class OvertimeRuleData:
    """Raw data representation of an overtime rule from the DB."""

    rule_id: str
    org_id: str
    multiplier: float
    priority: int
    applicable_job_titles: list[str] | None
    contract_id: str | None
