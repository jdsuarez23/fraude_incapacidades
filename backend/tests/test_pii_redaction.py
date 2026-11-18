import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from fraude_incapacidades.application.analysis_service import AnalysisService
from fraude_incapacidades.application.job_service import create_job, run_job
from fraude_incapacidades.application.report_service import forensic_prompt
from fraude_incapacidades.domain.scoring import signals_from_report
from fraude_incapacidades.infrastructure.pii_redaction import (
    PiiRedactionError,
    sanitized_pdf_for_analysis,
)


class MemoryStorage:
    upload_dir = Path("memory")

    def save(self, filename: str, content_hash: str, content: bytes) -> Path:
        return self.upload_dir / filename


class StubPdfAnalysis:
    def analyze(self, source, check_signature_region: bool = False) -> dict:
        return {"estado": "ok"}


class InspectingCrewRunner:
    def __init__(self):
        self.seen_text = ""
        self.seen_path = None

    async def run(self, inputs: dict, task_callback=None):
        self.seen_path = Path(inputs["file_path"])
        with fitz.open(self.seen_path) as document:
            self.seen_text = "\n".join(page.get_text() for page in document)
        return "{}"


def make_text_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "Paciente: Ana Maria Perez")
    page.insert_text((50, 80), "CC: 1234567890")
    page.insert_text((50, 110), "Email: ana@example.com")
    page.insert_text((50, 140), "Celular: 3001234567")
    page.insert_text((50, 170), "Diagnostico: J06.9")
    page.insert_text((50, 200), "Paciente:")
    page.insert_text((130, 200), "Carlos Perez")
    page.insert_text((50, 230), "Direccion: Calle 15 # 10-20")
    page.insert_text(
        (50, 260), "Paciente: Laura Gomez | Diagnostico: J18.9"
    )
    image_source = fitz.open()
    image_page = image_source.new_page()
    image_page.insert_text((10, 20), "Imagen decorativa")
    page.insert_image(
        fitz.Rect(250, 50, 350, 100),
        stream=image_page.get_pixmap().tobytes("png"),
    )
    document.set_metadata({"author": "Ana Maria Perez"})
    document.save(path)
    image_source.close()
    document.close()


class PiiRedactionTests(unittest.TestCase):
    def test_sanitized_pdf_masks_identifiers_and_removes_images(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.pdf"
            make_text_pdf(source)

            with sanitized_pdf_for_analysis(source) as sanitized:
                with fitz.open(sanitized) as document:
                    text = document[0].get_text()
                    self.assertNotIn("Ana Maria Perez", text)
                    self.assertNotIn("Carlos Perez", text)
                    self.assertNotIn("1234567890", text)
                    self.assertNotIn("ana@example.com", text)
                    self.assertNotIn("3001234567", text)
                    self.assertNotIn("Calle 15", text)
                    self.assertNotIn("Laura Gomez", text)
                    self.assertIn("Diagnostico: J06.9", text)
                    self.assertIn("Diagnostico: J18.9", text)
                    self.assertTrue(
                        all(image[2:4] == (1, 1) for image in document[0].get_images())
                    )
                    self.assertEqual(document.metadata["author"], "")

            self.assertFalse(sanitized.exists())

    def test_scanned_pdf_is_rejected_without_local_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scan.pdf"
            original = fitz.open()
            page = original.new_page()
            page.insert_text((50, 50), "Paciente: Ana Maria Perez")
            pixmap = page.get_pixmap()
            scanned = fitz.open()
            scanned_page = scanned.new_page()
            scanned_page.insert_image(scanned_page.rect, stream=pixmap.tobytes("png"))
            scanned.save(source)
            original.close()
            scanned.close()

            with self.assertRaisesRegex(PiiRedactionError, "OCR local"):
                with sanitized_pdf_for_analysis(source):
                    self.fail("An unredacted scanned document must not be yielded")

    def test_analysis_service_sends_only_sanitized_pdf_to_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.pdf"
            make_text_pdf(source)
            runner = InspectingCrewRunner()
            service = AnalysisService(MemoryStorage(), StubPdfAnalysis(), runner)

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                asyncio.run(
                    service.analyze_document(source, {"forense": {"estado": "ok"}})
                )

            self.assertNotEqual(runner.seen_path, source)
            self.assertNotIn("Ana Maria Perez", runner.seen_text)
            self.assertNotIn("Carlos Perez", runner.seen_text)
            self.assertNotIn("1234567890", runner.seen_text)
            self.assertNotIn("ana@example.com", runner.seen_text)
            self.assertNotIn("3001234567", runner.seen_text)
            self.assertIn("Diagnostico: J06.9", runner.seen_text)
            self.assertFalse(runner.seen_path.exists())

    def test_job_service_sends_only_sanitized_pdf_to_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.pdf"
            make_text_pdf(source)
            runner = InspectingCrewRunner()
            job_id = create_job({"forense": {"estado": "ok"}}, source)

            asyncio.run(run_job(job_id, runner))

            self.assertNotEqual(runner.seen_path, source)
            self.assertNotIn("Ana Maria Perez", runner.seen_text)
            self.assertNotIn("1234567890", runner.seen_text)
            self.assertNotIn("ana@example.com", runner.seen_text)
            self.assertNotIn("3001234567", runner.seen_text)
            self.assertFalse(runner.seen_path.exists())

    def test_forensic_prompt_does_not_send_free_text_metadata(self):
        prompt = forensic_prompt(
            {
                "estado": "editor_grafico",
                "creador": "Ana Maria Perez",
                "productor": "Ana Maria Perez",
                "editor_detectado": "canva",
                "alertas": [
                    {"nivel": "alta", "texto": "Autor: Ana Maria Perez"}
                ],
            }
        )

        self.assertNotIn("Ana Maria Perez", prompt)
        self.assertIn("canva", prompt)

    def test_signature_hidden_by_anonymization_is_not_scored_as_absent(self):
        signals = signals_from_report(
            {
                "datos_extraidos": {
                    "entidad": {
                        "firma_sello": "No evaluable por anonimización"
                    }
                }
            },
            {"estado": "ok"},
        )

        self.assertNotIn("firma_visible", signals)


if __name__ == "__main__":
    unittest.main()
