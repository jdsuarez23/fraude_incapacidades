from __future__ import annotations

from crewai.tools import BaseTool

class OSINTSearchTool(BaseTool):
    name: str = "Búsqueda Web OSINT"
    description: str = (
        "Busca en la web (DuckDuckGo) información sobre clínicas, médicos, EPS o IPS "
        "para confirmar existencia, reportes de fraude u otras alertas OSINT en Colombia."
    )

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query + " Colombia fraude incapacidad", max_results=5)
            if not results:
                return "No se encontraron resultados relevantes en la web."
            output = []
            for r in results:
                output.append(f"• {r.get('title', '')}\n  {r.get('body', '')}\n  URL: {r.get('href', '')}")
            return "\n\n".join(output)
        except Exception as e:
            return f"Error en búsqueda web: {e}. Continúa el análisis sin esta verificación."
