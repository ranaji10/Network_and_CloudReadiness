"""Loads scoring profiles and domain definitions from config/ (YAML). Validated with pydantic so a
typo in configuration fails fast with a readable message rather than silently skewing a score."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class CheckDef(BaseModel):
    id: str
    title: str
    points: float = 5
    ccm: list[str] = []
    signals: list[str] = []
    strong_signals: list[str] = []
    negative_signals: list[str] = []
    doc_classes: list[str] = []
    question: str = ""
    tags: list[str] = []


class PillarDef(BaseModel):
    id: str
    name: str
    weight: float
    description: str = ""
    checks: list[CheckDef]

    @property
    def max_points(self) -> float:
        return sum(c.points for c in self.checks)


class DomainDef(BaseModel):
    id: str
    name: str
    version: str = "1"
    description: str = ""
    pillars: list[PillarDef]

    @model_validator(mode="after")
    def _unique_ids(self) -> DomainDef:
        ids = [c.id for p in self.pillars for c in p.checks]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate check ids in domain {self.id}: {sorted(dupes)}")
        return self


class DomainWeight(BaseModel):
    id: str
    weight: float


class ProfileRules(BaseModel):
    met_min_signals: int = 2
    partial_points_ratio: float = 0.5
    negative_overrides: bool = True
    llm_override_min_confidence: float = 0.6


class Profile(BaseModel):
    id: str
    name: str
    version: str = "1"
    description: str = ""
    domains: list[DomainWeight]
    thresholds: dict[str, float] = Field(
        default_factory=lambda: {"high_confidence_coverage": 70.0, "grade_a": 85.0, "grade_b": 70.0, "grade_c": 50.0}
    )
    rules: ProfileRules = ProfileRules()
    target_providers: list[str] = ["gcp", "aws", "oss"]
    max_recommendations: int = 40


def load_profile(config_dir: Path, profile_id: str) -> Profile:
    path = config_dir / "profiles" / f"{profile_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown profile '{profile_id}' (expected {path})")
    return Profile.model_validate(yaml.safe_load(path.read_text()))


def list_profiles(config_dir: Path) -> list[Profile]:
    return [
        Profile.model_validate(yaml.safe_load(p.read_text())) for p in sorted((config_dir / "profiles").glob("*.yaml"))
    ]


def load_domain(config_dir: Path, domain_id: str) -> DomainDef:
    path = config_dir / "scoring" / f"{domain_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown scoring domain '{domain_id}' (expected {path})")
    return DomainDef.model_validate(yaml.safe_load(path.read_text()))


def load_domains(config_dir: Path, profile: Profile) -> list[DomainDef]:
    return [load_domain(config_dir, d.id) for d in profile.domains]
