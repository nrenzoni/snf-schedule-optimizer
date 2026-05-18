from dataclasses import dataclass

from snf_schedule_optimizer.domain.specifications import Specification


@dataclass
class NumberSpec(Specification[int]):
    threshold: int

    def is_satisfied_by(self, candidate: int) -> bool:
        return candidate > self.threshold


def test_specification_and() -> None:
    gt5 = NumberSpec(threshold=5)
    lt10 = NumberSpec(threshold=10).not_()
    combined = gt5.and_(lt10)
    assert combined.is_satisfied_by(7)
    assert not combined.is_satisfied_by(3)
    assert not combined.is_satisfied_by(12)
