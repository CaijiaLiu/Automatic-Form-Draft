from dataclasses import dataclass

@dataclass(frozen=True)
class Fact:
    category: str
    value: str
    date: str
    filename: str
    location: str
    evidence: str
    review_reason: str = ''

