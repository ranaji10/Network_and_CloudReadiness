import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("find_agent_engine", Path("scripts/find_agent_engine.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_pick_newest_matching_instance():
    engines = [
        {
            "name": "projects/p/locations/r/reasoningEngines/111",
            "displayName": "readiness-assessor",
            "createTime": "2026-10-23T14:27:00Z",
        },
        {
            "name": "projects/p/locations/r/reasoningEngines/222",
            "displayName": "readiness-assessor",
            "createTime": "2026-10-23T15:03:00Z",
        },
        {
            "name": "projects/p/locations/r/reasoningEngines/333",
            "displayName": "other",
            "createTime": "2026-10-23T16:00:00Z",
        },
    ]
    assert mod.pick(engines, "readiness-assessor") == "222"
    assert mod.pick(engines, "missing") == ""
    assert mod.pick([], "readiness-assessor") == ""
