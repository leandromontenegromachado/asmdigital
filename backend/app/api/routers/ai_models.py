from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import AiModel, AiModelAssignment
from app.schemas.ai_models import (
    AiModelAssignmentOut,
    AiModelAssignmentUpdate,
    AiModelCreate,
    AiModelOut,
    AiModelUpdate,
)
from app.services.ai_model_service import AI_MODEL_FEATURES, SUPPORTED_PROVIDERS, provider_label

router = APIRouter(prefix="/ai-models", tags=["ai-models"])


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_model_payload(data: dict, *, partial: bool = False) -> dict:
    for key in ("name", "provider", "model_id", "description", "api_key_env"):
        if key in data:
            data[key] = _clean_string(data[key])
    if not partial and not data.get("name"):
        raise HTTPException(status_code=400, detail="Informe o nome do modelo")
    if not partial and not data.get("provider"):
        raise HTTPException(status_code=400, detail="Informe o provedor")
    if not partial and not data.get("model_id"):
        raise HTTPException(status_code=400, detail="Informe o identificador do modelo")
    if "name" in data and not data.get("name"):
        raise HTTPException(status_code=400, detail="Informe o nome do modelo")
    if "provider" in data and not data.get("provider"):
        raise HTTPException(status_code=400, detail="Informe o provedor")
    if "model_id" in data and not data.get("model_id"):
        raise HTTPException(status_code=400, detail="Informe o identificador do modelo")
    if data.get("provider"):
        data["provider"] = str(data["provider"]).lower()
    return data


def _model_out(model: AiModel) -> AiModelOut:
    return AiModelOut.model_validate(model)


def _assignment_out(assignment: AiModelAssignment) -> AiModelAssignmentOut:
    model = assignment.model
    return AiModelAssignmentOut(
        id=assignment.id,
        feature_key=assignment.feature_key,
        feature_label=AI_MODEL_FEATURES.get(assignment.feature_key, assignment.feature_key),
        model_id=assignment.model_id,
        model_name=model.name if model else "-",
        provider=model.provider if model else "-",
        provider_label=provider_label(model.provider) if model else "-",
        provider_supported=bool(model and model.provider in SUPPORTED_PROVIDERS),
        external_model_id=model.model_id if model else "-",
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _set_default_if_needed(db: Session, model: AiModel, is_default: bool | None) -> None:
    if is_default:
        db.query(AiModel).filter(AiModel.id != model.id).update({AiModel.is_default: False})
        model.is_default = True


@router.get("", response_model=list[AiModelOut])
def list_models(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(AiModel).order_by(AiModel.is_default.desc(), AiModel.name.asc()).all()


@router.post("", response_model=AiModelOut, status_code=status.HTTP_201_CREATED)
def create_model(payload: AiModelCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    data = _normalize_model_payload(payload.model_dump())
    model = AiModel(**data)
    db.add(model)
    try:
        db.flush()
        _set_default_if_needed(db, model, data.get("is_default"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Modelo ja cadastrado para este provedor") from exc
    db.refresh(model)
    return _model_out(model)


@router.get("/features")
def list_features(_user=Depends(get_current_user)):
    return [{"key": key, "label": label} for key, label in AI_MODEL_FEATURES.items()]


@router.get("/assignments", response_model=list[AiModelAssignmentOut])
def list_assignments(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    existing = {item.feature_key: item for item in db.query(AiModelAssignment).all()}
    return [_assignment_out(existing[key]) for key in AI_MODEL_FEATURES if key in existing]


@router.put("/assignments/{feature_key}", response_model=AiModelAssignmentOut)
def update_assignment(
    feature_key: str,
    payload: AiModelAssignmentUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    key = feature_key.strip().lower()
    if key not in AI_MODEL_FEATURES:
        raise HTTPException(status_code=404, detail="Funcionalidade nao encontrada")
    model = db.query(AiModel).filter(AiModel.id == payload.model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    if not model.is_active:
        raise HTTPException(status_code=400, detail="Modelo inativo")
    assignment = db.query(AiModelAssignment).filter(AiModelAssignment.feature_key == key).first()
    if not assignment:
        assignment = AiModelAssignment(feature_key=key, model_id=model.id)
        db.add(assignment)
    else:
        assignment.model_id = model.id
    db.commit()
    db.refresh(assignment)
    return _assignment_out(assignment)


@router.get("/{model_id}", response_model=AiModelOut)
def get_model(model_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    model = db.query(AiModel).filter(AiModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    return _model_out(model)


@router.put("/{model_id}", response_model=AiModelOut)
def update_model(
    model_id: int,
    payload: AiModelUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    model = db.query(AiModel).filter(AiModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    data = _normalize_model_payload(payload.model_dump(exclude_unset=True), partial=True)
    for key, value in data.items():
        if key != "is_default":
            setattr(model, key, value)
    _set_default_if_needed(db, model, data.get("is_default"))
    if data.get("is_default") is False:
        model.is_default = False
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Modelo ja cadastrado para este provedor") from exc
    db.refresh(model)
    return _model_out(model)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    model = db.query(AiModel).filter(AiModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado")
    assigned = db.query(AiModelAssignment).filter(AiModelAssignment.model_id == model.id).first()
    if assigned:
        raise HTTPException(status_code=409, detail="Modelo esta vinculado a uma funcionalidade")
    db.delete(model)
    db.commit()
    return None
