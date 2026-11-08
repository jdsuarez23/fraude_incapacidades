import os


def get_openai_model() -> str:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip()
    if not model:
        raise ValueError("OPENAI_MODEL no puede estar vacío.")
    return model
