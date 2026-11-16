from pathlib import Path

from fraude_incapacidades.forensics import analyze_pdf


class PyMuPDFAnalysis:
    def analyze(
        self, source: bytes | str | Path, check_signature_region: bool = False
    ) -> dict:
        return analyze_pdf(source, check_signature_region=check_signature_region)
