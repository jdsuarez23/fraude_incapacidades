import unittest
from pathlib import Path

from fraude_incapacidades.api.routers.analysis import router as analysis_router
from fraude_incapacidades.api.routers.benchmark import router as benchmark_router
from fraude_incapacidades.application.analysis_service import AnalysisService
from fraude_incapacidades.application.report_service import ReportService
from fraude_incapacidades.domain.scoring import (
    cie10_standard_days,
    evaluate as domain_evaluate,
)
from fraude_incapacidades.scoring import evaluate as legacy_evaluate
from fraude_incapacidades.tools.cie10_tool import CIE10_DATABASE
from fraude_incapacidades.validation import validate_upload
from fraude_incapacidades.domain.cie10_catalog import (
    CIE10_DATABASE as domain_cie10_database,
)


class MemoryStorage:
    upload_dir = Path("memory")

    def __init__(self):
        self.saved = None

    def save(self, filename: str, content_hash: str, content: bytes) -> Path:
        self.saved = (filename, content_hash, content)
        return self.upload_dir / filename


class StubPdfAnalysis:
    def __init__(self):
        self.sources = []

    def analyze(self, source, check_signature_region: bool = False) -> dict:
        self.sources.append((source, check_signature_region))
        return {"estado": "ok"}


class StubCrewRunner:
    async def run(self, inputs: dict, task_callback=None):
        return "{}"


class StubPdfExporter:
    def export(self, payload: dict) -> bytes:
        return b"pdf"


class LayeredBackendTests(unittest.TestCase):
    def test_analysis_service_uses_injected_adapters(self):
        storage = MemoryStorage()
        pdf_analysis = StubPdfAnalysis()
        service = AnalysisService(storage, pdf_analysis, StubCrewRunner())

        validation, path = service.validate_and_store(
            "sample.pdf", b"%PDF-1.4\n%%EOF"
        )

        self.assertTrue(validation["valido"])
        self.assertEqual(path, Path("memory") / "sample.pdf")
        self.assertEqual(storage.saved[0], "sample.pdf")
        self.assertEqual(pdf_analysis.sources, [(b"%PDF-1.4\n%%EOF", False)])
        self.assertEqual(validation["forense"], {"estado": "ok"})

    def test_invalid_upload_is_not_stored_or_analyzed(self):
        storage = MemoryStorage()
        pdf_analysis = StubPdfAnalysis()
        service = AnalysisService(storage, pdf_analysis, StubCrewRunner())

        validation, path = service.validate_and_store("sample.txt", b"not a PDF")

        self.assertFalse(validation["valido"])
        self.assertIsNone(path)
        self.assertIsNone(storage.saved)
        self.assertEqual(pdf_analysis.sources, [])

    def test_report_service_uses_injected_pdf_exporter(self):
        service = ReportService(StubPdfExporter())

        self.assertEqual(service.export_pdf({"informe": {}}), b"pdf")

    def test_crewai_crews_are_isolated_and_tasks_have_explicit_context(self):
        from fraude_incapacidades.crew import build_crew

        first = build_crew()
        second = build_crew()

        self.assertIsNot(first, second)
        self.assertEqual(len(first.tasks), 3)
        self.assertIsNot(first.tasks[0], second.tasks[0])
        self.assertEqual(first.tasks[1].context, [first.tasks[0]])
        self.assertEqual(
            first.tasks[2].context,
            [first.tasks[0], first.tasks[1]],
        )

    def test_legacy_validation_and_scoring_imports_remain_available(self):
        self.assertTrue(validate_upload("sample.pdf", b"%PDF-").valido)
        self.assertIs(legacy_evaluate, domain_evaluate)
        self.assertIs(CIE10_DATABASE, domain_cie10_database)
        self.assertEqual(cie10_standard_days("J069"), 7)

    def test_http_routers_keep_existing_endpoint_paths(self):
        paths = {route.path for route in analysis_router.routes}
        paths.update(route.path for route in benchmark_router.routes)
        analysis_handlers = {
            route.path: route.endpoint.__name__ for route in analysis_router.routes
        }

        self.assertTrue(
            {
                "/api/validate",
                "/api/jobs",
                "/api/jobs/{job_id}",
                "/api/jobs/{job_id}/retry",
                "/api/analyze",
                "/api/export/pdf",
                "/api/benchmark/run",
                "/api/benchmark/agent",
                "/api/benchmark/custom",
            }.issubset(paths)
        )
        self.assertEqual(analysis_handlers["/api/jobs"], "create_job")
        self.assertEqual(analysis_handlers["/api/jobs/{job_id}"], "get_job")
        self.assertEqual(
            analysis_handlers["/api/jobs/{job_id}/retry"], "retry_job"
        )


if __name__ == "__main__":
    unittest.main()
