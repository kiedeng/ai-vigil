from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import EvaluatorTestOut, SettingsOut, SettingsUpdate
from ..security import get_current_user
from ..services.ai_evaluator import evaluate_response
from ..services.settings import effective_settings, set_setting_value


router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=SettingsOut)
def get_settings_endpoint(db: Session = Depends(get_db)) -> SettingsOut:
    return SettingsOut(**effective_settings(db))


@router.put("", response_model=SettingsOut)
def update_settings_endpoint(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            set_setting_value(db, key, value)
    return SettingsOut(**effective_settings(db))


@router.post("/evaluator/test", response_model=EvaluatorTestOut)
async def test_evaluator(db: Session = Depends(get_db)) -> EvaluatorTestOut:
    result = await evaluate_response(
        db,
        expectation="返回内容必须表示系统健康检查通过。",
        response_text='{"status":"ok","message":"AI Vigil evaluator test"}',
        evaluator_config={"timeout_seconds": 60, "min_confidence": 0},
    )
    return EvaluatorTestOut(
        status=str(result.get("status", "unknown")),
        passed=bool(result.get("passed")),
        reason=str(result.get("reason", "")),
        model=str(result.get("model", "")),
    )
