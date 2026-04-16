from sqlalchemy.orm import Session

from ..models import EvaluatorPrompt, ModelRule
from .new_api_instances import ensure_default_instance


DEFAULT_MODEL_RULES = [
    {"name": "DeepSeek Chat", "pattern": "deepseek*", "match_type": "glob", "check_type": "model_llm_chat", "priority": 10},
    {"name": "Qwen VL Vision", "pattern": "qwen-vl*", "match_type": "glob", "check_type": "model_vision_chat", "priority": 15},
    {"name": "BGE Reranker", "pattern": "bge-reranker*", "match_type": "glob", "check_type": "model_rerank", "priority": 19},
    {"name": "BGE Embedding", "pattern": "bge*", "match_type": "glob", "check_type": "model_embedding", "priority": 20},
    {"name": "Whisper ASR", "pattern": "whisper*", "match_type": "glob", "check_type": "model_audio_transcription", "priority": 30},
    {"name": "TTS Speech", "pattern": "tts*", "match_type": "glob", "check_type": "model_audio_speech", "priority": 40},
    {"name": "DALL-E Image", "pattern": "dall-e*", "match_type": "glob", "check_type": "model_image_generation", "priority": 50},
    {"name": "GPT Image", "pattern": "gpt-image*", "match_type": "glob", "check_type": "model_image_generation", "priority": 51},
    {"name": "Moderation", "pattern": "*moderation*", "match_type": "glob", "check_type": "model_moderation", "priority": 60},
]


def seed_defaults(db: Session) -> None:
    ensure_default_instance(db)
    for item in DEFAULT_MODEL_RULES:
        exists = db.query(ModelRule).filter(ModelRule.name == item["name"]).first()
        if exists:
            continue
        db.add(ModelRule(**item, enabled=True, request_config={}, validation_config={}))
    if not db.query(EvaluatorPrompt).filter(EvaluatorPrompt.name == "default", EvaluatorPrompt.version == 1).first():
        db.add(
            EvaluatorPrompt(
                name="default",
                version=1,
                active=True,
                prompt_template=(
                    "You are a strict monitoring evaluator. Judge whether the observed output satisfies the expectation.\n"
                    "Return JSON only with this shape: "
                    "{\"passed\": boolean, \"confidence\": number, \"score\": number, \"reason\": string}.\n"
                    "Expectation: {expectation}\nObserved output: {response_text}"
                ),
                output_schema={
                    "required": ["passed", "confidence", "score", "reason"],
                    "properties": {
                        "passed": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                },
            )
        )
    db.commit()
