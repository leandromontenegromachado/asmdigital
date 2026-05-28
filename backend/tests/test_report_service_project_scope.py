from app.models import Connector
from app.services.report_service import _connector_scoped_project_ids, _issue_matches_project_scope


def test_connector_project_scope_falls_back_to_configured_project():
    connector = Connector(id=1, config_json={"project_ids": ["ASM-DEM"]})

    assert _connector_scoped_project_ids(connector, []) == ["asm-dem"]
    assert _connector_scoped_project_ids(connector, ["outro-setor"]) == ["asm-dem"]
    assert _connector_scoped_project_ids(connector, ["asm-dem", "outro-setor"]) == ["asm-dem"]


def test_issue_project_scope_accepts_identifier_or_name_only():
    issue = {"project": {"id": 10, "identifier": "asm-dem", "name": "ASM DEM"}}
    other_issue = {"project": {"id": 11, "identifier": "outro-setor", "name": "Outro Setor"}}

    assert _issue_matches_project_scope(issue, "ASM-DEM")
    assert _issue_matches_project_scope(issue, "10")
    assert not _issue_matches_project_scope(other_issue, "ASM-DEM")


def test_issue_project_scope_accepts_redmine_name_for_abbreviated_identifier():
    issue = {"project": {"id": 10, "name": "ASM Demandas"}}

    assert _issue_matches_project_scope(issue, "asm-dem")
