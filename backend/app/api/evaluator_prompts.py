from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EvaluatorPrompt
from ..schemas import EvaluatorPromptCreate, EvaluatorPromptOut, EvaluatorPromptUpdate
from ..security import get_current_user


router = APIRouter(prefix="/evaluator-prompts", tags=["evaluator-prompts"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[EvaluatorPromptOut])
def list_prompts(db: Session = Depends(get_db)) -> list[EvaluatorPrompt]:
    return db.query(EvaluatorPrompt).order_by(EvaluatorPrompt.name.asc(), EvaluatorPrompt.version.desc()).all()


@router.post("", response_model=EvaluatorPromptOut, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: EvaluatorPromptCreate, db: Session = Depends(get_db)) -> EvaluatorPrompt:
    row = EvaluatorPrompt(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{prompt_id}", response_model=EvaluatorPromptOut)
def update_prompt(prompt_id: int, payload: EvaluatorPromptUpdate, db: Session = Depends(get_db)) -> EvaluatorPrompt:
    row = db.query(EvaluatorPrompt).filter(EvaluatorPrompt.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)) -> None:
    row = db.query(EvaluatorPrompt).filter(EvaluatorPrompt.id == prompt_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(row)
    db.commit()

