from pydantic import BaseModel


class AzureDevOpsHours(BaseModel):
    original: float = 0
    remaining: float = 0
    completed: float = 0


class AzureDevOpsLinkedItem(BaseModel):
    id: int
    type: str | None = None
    title: str | None = None
    state: str | None = None


class AzureDevOpsWorkItemOut(BaseModel):
    id: int
    type: str | None = None
    title: str | None = None
    state: str | None = None
    area_path: str | None = None
    iteration_path: str | None = None
    assigned_to: str | None = None
    hours: AzureDevOpsHours
    parent: AzureDevOpsLinkedItem | None = None
    epic: AzureDevOpsLinkedItem | None = None


class AzureDevOpsTotalsOut(BaseModel):
    total: int
    with_epic: int
    without_epic: int
    by_state: dict[str, int]
    hours: AzureDevOpsHours


class AzureDevOpsDiagnosticItemOut(BaseModel):
    id: int
    title: str | None = None
    state: str | None = None
    type: str | None = None
    parent: AzureDevOpsLinkedItem | None = None
    epic: AzureDevOpsLinkedItem | None = None


class AzureDevOpsDiagnosticByUserOut(BaseModel):
    user: str
    count: int
    items: list[AzureDevOpsDiagnosticItemOut]


class AzureDevOpsDiagnosticGroupOut(BaseModel):
    total: int
    users: list[AzureDevOpsDiagnosticByUserOut]


class AzureDevOpsDiagnosticsOut(BaseModel):
    pbi_without_task: AzureDevOpsDiagnosticGroupOut
    tasks_without_hours: AzureDevOpsDiagnosticGroupOut


class AzureDevOpsSnapshotOut(BaseModel):
    items: list[AzureDevOpsWorkItemOut]
    totals: AzureDevOpsTotalsOut
    diagnostics: AzureDevOpsDiagnosticsOut
