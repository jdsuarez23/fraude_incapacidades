from fraude_incapacidades.export_pdf import build_pdf


class PyMuPDFReportExporter:
    def export(self, payload: dict) -> bytes:
        return build_pdf(payload)
