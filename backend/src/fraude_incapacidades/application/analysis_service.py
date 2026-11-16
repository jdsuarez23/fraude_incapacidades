from pathlib import Path

from fraude_incapacidades.domain.upload_validation import validate_upload

from .ports import CrewRunner, PdfAnalysis, UploadStorage
from .report_service import (
    AnalysisResponse,
    enrich_report,
    forensic_prompt,
    parse_crew_result,
)
from .runtime import CREW_LOCK


def api_key_error() -> str | None:
    import os

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return "Configura OPENAI_API_KEY en el archivo .env para analizar documentos."
    return None


class AnalysisService:
    def __init__(
        self,
        storage: UploadStorage,
        pdf_analysis: PdfAnalysis,
        crew_runner: CrewRunner,
    ):
        self.storage = storage
        self.pdf_analysis = pdf_analysis
        self.crew_runner = crew_runner

    def api_key_error(self) -> str | None:
        return api_key_error()

    def validate_and_store(
        self, filename: str, content: bytes
    ) -> tuple[dict, Path | None]:
        validation = validate_upload(filename, content)
        if not validation.valido:
            return validation.to_dict(), None

        path = self.storage.save(validation.nombre, validation.sha256, content)
        result = validation.to_dict()
        try:
            result["forense"] = self.pdf_analysis.analyze(content)
        except Exception as exc:  # noqa: BLE001
            result["forense"] = {
                "estado": "ok",
                "alertas": [
                    {
                        "nivel": "leve",
                        "texto": f"No se pudieron leer los metadatos: {exc}",
                    }
                ],
            }
        return result, path

    async def analyze_document(
        self, path: Path, validation: dict
    ) -> AnalysisResponse:
        if error := self.api_key_error():
            return AnalysisResponse(
                status="error", error=error, validacion=validation
            )

        try:
            async with CREW_LOCK:
                    result = await self.crew_runner.run(
                        {
                        "file_path": str(path),
                        "metadatos_forenses": forensic_prompt(
                            validation.get("forense")
                        ),
                        },
                        task_callback=None,
                )
            report, raw_text = parse_crew_result(result)
            enrich_report(report, validation.get("forense"))
            return AnalysisResponse(
                status="success",
                report=report,
                raw_report=raw_text,
                validacion=validation,
            )
        except Exception as exc:  # noqa: BLE001
            return AnalysisResponse(status="error", error=str(exc))
