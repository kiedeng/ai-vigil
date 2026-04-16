from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ModelRule
from ..schemas import ModelRuleCreate, ModelRuleOut, ModelRuleUpdate
from ..security import get_current_user


router = APIRouter(prefix="/model-rules", tags=["model-rules"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ModelRuleOut])
def list_rules(db: Session = Depends(get_db)) -> list[ModelRule]:
    return db.query(ModelRule).order_by(ModelRule.priority.asc(), ModelRule.id.asc()).all()


@router.post("", response_model=ModelRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(payload: ModelRuleCreate, db: Session = Depends(get_db)) -> ModelRule:
    rule = ModelRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=ModelRuleOut)
def update_rule(rule_id: int, payload: ModelRuleUpdate, db: Session = Depends(get_db)) -> ModelRule:
    rule = db.query(ModelRule).filter(ModelRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = db.query(ModelRule).filter(ModelRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()

