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
    # Optional per-profile emphasis inside a domain: {domain_id: {pillar_id: weight}}. Pillars not listed
    # keep the weight from config/scoring/<domain>.yaml. Lets an industry profile stress, say, audit
    # logging or data protection without forking the domain definition.
    pillar_weight_overrides: dict[str, dict[str, float]] = {}

    @model_validator(mode="after")
    def _overrides_are_consistent(self) -> Profile:
        listed = {d.id for d in self.domains}
        for dom_id, pillars in self.pillar_weight_overrides.items():
            if dom_id not in listed:
                raise ValueError(
                    f"profile {self.id}: pillar_weight_overrides names domain '{dom_id}' which is not in domains "
                    f"{sorted(listed)}"
                )
            for pid, w in pillars.items():
                if w <= 0:
                    raise ValueError(f"profile {self.id}: pillar weight override {dom_id}.{pid} must be > 0, got {w}")
        return self


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


def apply_pillar_weight_overrides(domain: DomainDef, overrides: dict[str, float]) -> DomainDef:
    """Returns a copy of ``domain`` with the listed pillar weights replaced. Unknown pillar ids are an
    error so a typo in a profile fails at load time instead of silently keeping the default weight."""
    known = {p.id for p in domain.pillars}
    unknown = sorted(set(overrides) - known)
    if unknown:
        raise ValueError(
            f"pillar_weight_overrides for domain '{domain.id}' names unknown pillar(s) {unknown}; "
            f"known pillars: {sorted(known)}"
        )
    pillars = [p.model_copy(update={"weight": overrides.get(p.id, p.weight)}) for p in domain.pillars]
    return domain.model_copy(update={"pillars": pillars})


def load_domains(config_dir: Path, profile: Profile) -> list[DomainDef]:
    """Loads every domain the profile lists, with the profile's pillar weight overrides applied. This is
    the one place overrides are resolved, so scoring, recommendations and the report all see them."""
    domains: list[DomainDef] = []
    for d in profile.domains:
        dom = load_domain(config_dir, d.id)
        overrides = profile.pillar_weight_overrides.get(d.id)
        if overrides:
            dom = apply_pillar_weight_overrides(dom, overrides)
        domains.append(dom)
    return domains
