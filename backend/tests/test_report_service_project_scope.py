from app.models import Connector
from app.services.report_service import _connector_scoped_project_ids, _issue_matches_project_scope, _issue_report_metadata, _issue_url


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


def test_issue_metadata_calculates_days_since_update(monkeypatch):
    class FixedDate:
        @classmethod
        def today(cls):
            from datetime import date

            return date(2026, 5, 28)

    monkeypatch.setattr("app.services.report_service.date", FixedDate)

    metadata = _issue_report_metadata({"id": 1, "updated_on": "2026-05-20T10:00:00Z"})

    assert metadata["days_since_update"] == 8


def test_issue_url_uses_redmine_root_when_base_url_is_project_scoped():
    assert _issue_url("https://redmine.intra.rs.gov.br/projects/asm-dem", 329325) == "https://redmine.intra.rs.gov.br/issues/329325"
