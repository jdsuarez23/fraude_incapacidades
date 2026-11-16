from fraude_incapacidades.application.analysis_service import AnalysisService
from fraude_incapacidades.infrastructure.crewai_runner import CrewAiRunner
from fraude_incapacidades.infrastructure.pdf_analysis import PyMuPDFAnalysis
from fraude_incapacidades.infrastructure.pdf_exporter import PyMuPDFReportExporter
from fraude_incapacidades.infrastructure.upload_storage import LocalUploadStorage
from fraude_incapacidades.application.report_service import ReportService

upload_storage = LocalUploadStorage()
pdf_analysis = PyMuPDFAnalysis()
crew_runner = CrewAiRunner()
analysis_service = AnalysisService(upload_storage, pdf_analysis, crew_runner)
report_service = ReportService(PyMuPDFReportExporter())
