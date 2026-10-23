"""Turns check results into prioritised recommendations.

* not_met / partial -> an *action* with provider options (GCP / AWS / open source / process) from
  config/recommendations/catalog.yaml, ordered by the profile's provider preference.
* unknown -> a *discovery* item: the CAIQ questions for the mapped CCM controls, so the next round of
  documents or interviews closes the evidence gap (the V1 questionnaire flow)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from readiness.models import CheckStatus, DomainScore, Recommendation, RecommendationOption
from readiness.scoring.catalog import caiq_questions
from readiness.scoring.profiles import Profile


class CatalogEntry(BaseModel):
    check_id: str
    title: str
    rationale: str = ""
    effort: str = "M"
    impact: str = "medium"
    options: list[RecommendationOption] = []


def load_catalog(config_dir: Path) -> dict[str, CatalogEntry]:
    path = config_dir / "recommendations" / "catalog.yaml"
    data = yaml.safe_load(path.read_text())
    entries = [CatalogEntry.model_validate(e) for e in data["recommendations"]]
    return {e.check_id: e for e in entries}


_IMPACT_W = {"high": 1.5, "medium": 1.0, "low": 0.6}
_EFFORT_W = {"S": 1.2, "M": 1.0, "L": 0.8}


def recommend(domains: list[DomainScore], profile: Profile, config_dir: Path) -> list[Recommendation]:
    catalog = load_catalog(config_dir)
    pref = {p: i for i, p in enumerate(profile.target_providers)}
    dom_w = {d.id: d.weight for d in profile.domains}
    out: list[Recommendation] = []
    for d in domains:
        for p in d.pillars:
            for r in p.checks:
                if r.status == CheckStatus.MET:
                    continue
                lost = r.max_points - r.points
                base = lost * p.weight * dom_w.get(d.domain_id, 1) / 100
                entry = catalog.get(r.check_id)
                if r.status == CheckStatus.UNKNOWN:
                    out.append(
                        Recommendation(
                            id=f"D-{r.check_id}",
                            check_id=r.check_id,
                            domain_id=d.domain_id,
                            pillar_id=p.pillar_id,
                            title=f"Provide evidence for: {r.title}",
                            rationale="No document covered this check. Supply the artefact or answer the questions.",
                            priority=round(base * 0.5, 3),
                            effort="S",
                            impact="medium",
                            kind="discovery",
                            caiq_questions=caiq_questions(r.ccm_controls)[:6],
                            ccm_controls=r.ccm_controls,
                        )
                    )
                    continue
                if entry:
                    options = sorted(entry.options, key=lambda o: pref.get(o.provider, 99))
                    options = [o for o in options if o.provider in pref or o.provider == "process"]
                    title, rationale, effort, impact = (
                        entry.title,
                        entry.rationale,
                        entry.effort,
                        entry.impact,
                    )
                else:
                    options, title, rationale, effort, impact = (
                        [],
                        f"Remediate: {r.title}",
                        r.rationale,
                        "M",
                        "medium",
                    )
                out.append(
                    Recommendation(
                        id=f"A-{r.check_id}",
                        check_id=r.check_id,
                        domain_id=d.domain_id,
                        pillar_id=p.pillar_id,
                        title=title,
                        rationale=rationale or r.rationale,
                        priority=round(base * _IMPACT_W.get(impact, 1) * _EFFORT_W.get(effort, 1), 3),
                        effort=effort,
                        impact=impact,
                        kind="action",
                        options=options,
                        ccm_controls=r.ccm_controls,
                    )
                )
    out.sort(key=lambda x: (-x.priority, x.id))
    return out[: profile.max_recommendations]
