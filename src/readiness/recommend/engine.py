"""Turns check results into prioritised recommendations.

* not_met / partial -> an *action* with provider options (GCP / AWS / open source / process) from
  config/recommendations/catalog.yaml, ordered by the profile's provider preference.
* unknown -> a *discovery* item: the CAIQ questions for the mapped CCM controls, so the next round of
  documents or interviews closes the evidence gap (the V1 questionnaire flow).

De-duplication (REC-06): several checks are often closed by rolling out the same product (one identity
provider closes SSO, MFA and cloud federation). When the profile rule `dedupe_by_product` is on, actions
whose *preferred* option (the first one after provider-preference ordering) belongs to the same product
family are merged into one action that lists every check it closes (`closes_check_ids`). The family key
is `<provider>:<family>` where `family` is the option's explicit `family` tag in the catalog, falling back
to the product name lower-cased and trimmed. Discovery items are never merged.

Cost ceiling (REC-04): every catalog option carries an indicative monthly `cost_band`. When the profile rule
`max_cost_band` is set, options above that band are dropped before the preferred option (and so the family)
is chosen. An action that loses every option is kept, with no options and a sentence appended to its
rationale, so the finding is not silently lost. A merged action shows the lead member's options, and with
them the lead option's band."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from readiness.models import COST_BAND_RANK, CheckStatus, DomainScore, Recommendation, RecommendationOption
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
# Rank used when merging: the merged action carries the largest effort and impact of its members.
_IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}
_EFFORT_RANK = {"S": 0, "M": 1, "L": 2}


def family_key(option: RecommendationOption) -> str:
    """Product-family key of one option: `<provider>:<family or normalised product>`."""
    fam = option.family.strip().lower() or " ".join(option.product.strip().lower().split())
    return f"{option.provider}:{fam}"


def _max_by(values: list[str], rank: dict[str, int]) -> str:
    return max(values, key=lambda v: rank.get(v, -1))


NO_OPTION_WITHIN_CEILING = "No option within the cost ceiling"


def within_cost_ceiling(option: RecommendationOption, max_band: str | None) -> bool:
    """True when the option's band is at or below `max_band`. No ceiling, or an option without a band
    (a catalog that predates REC-04), keeps the option: the filter never hides what it cannot judge."""
    if max_band is None or option.cost_band is None:
        return True
    return COST_BAND_RANK[option.cost_band] <= COST_BAND_RANK[max_band]


def merge_by_family(actions: list[Recommendation]) -> list[Recommendation]:
    """Merge actions whose preferred option shares a product family. Input order is irrelevant: the
    member with the highest priority provides id, check_id, title, rationale, options and position.
    Priority is the sum of the members' priorities (the family closes all of them), effort and impact
    are the maxima, CCM controls are the union in first-seen order."""
    groups: dict[str, list[Recommendation]] = {}
    singles: list[Recommendation] = []
    for a in actions:
        if a.kind != "action" or not a.options:
            singles.append(a)  # nothing to key on: process-only or catalog-less actions stay separate
            continue
        groups.setdefault(family_key(a.options[0]), []).append(a)
    out = list(singles)
    for key, members in groups.items():
        members.sort(key=lambda x: (-x.priority, x.id))
        lead = members[0]
        if len(members) == 1:
            out.append(lead.model_copy(update={"family": key}))
            continue
        controls: list[str] = []
        ids: list[str] = []
        titles: list[str] = []
        for m in members:
            controls.extend(c for c in m.ccm_controls if c not in controls)
            ids.extend(m.closes_check_ids or [m.check_id])
            titles.extend(m.closes_titles or [m.title])
        out.append(
            lead.model_copy(
                update={
                    "priority": round(sum(m.priority for m in members), 3),
                    "effort": _max_by([m.effort for m in members], _EFFORT_RANK),
                    "impact": _max_by([m.impact for m in members], _IMPACT_RANK),
                    "family": key,
                    "closes_check_ids": ids,
                    "closes_titles": titles,
                    "ccm_controls": controls,
                }
            )
        )
    return out


def recommend(domains: list[DomainScore], profile: Profile, config_dir: Path) -> list[Recommendation]:
    catalog = load_catalog(config_dir)
    pref = {p: i for i, p in enumerate(profile.target_providers)}
    dom_w = {d.id: d.weight for d in profile.domains}
    actions: list[Recommendation] = []
    discovery: list[Recommendation] = []
    for d in domains:
        for p in d.pillars:
            for r in p.checks:
                if r.status == CheckStatus.MET:
                    continue
                lost = r.max_points - r.points
                base = lost * p.weight * dom_w.get(d.domain_id, 1) / 100
                entry = catalog.get(r.check_id)
                if r.status == CheckStatus.UNKNOWN:
                    discovery.append(
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
                    ceiling = profile.rules.max_cost_band
                    affordable = [o for o in options if within_cost_ceiling(o, ceiling)]
                    if options and not affordable:
                        # keep the finding, say why no product is listed (the band legend explains the scale)
                        rationale = (
                            f"{rationale or r.rationale} {NO_OPTION_WITHIN_CEILING} "
                            f"(profile `max_cost_band: {ceiling}`); every catalog option for this check is above it."
                        ).strip()
                    options = affordable
                else:
                    options, title, rationale, effort, impact = (
                        [],
                        f"Remediate: {r.title}",
                        r.rationale,
                        "M",
                        "medium",
                    )
                actions.append(
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
                        family=family_key(options[0]) if options else "",
                        closes_check_ids=[r.check_id],
                        closes_titles=[r.title],
                    )
                )
    if profile.rules.dedupe_by_product:
        actions = merge_by_family(actions)
    out = actions + discovery
    out.sort(key=lambda x: (-x.priority, x.id))
    return out[: profile.max_recommendations]
