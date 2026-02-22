from __future__ import annotations

from crewai.tools import BaseTool


class OSINTSearchTool(BaseTool):
    name: str = "Busqueda Web OSINT"
    description: str = (
        "Busca en la web (DuckDuckGo) información sobre clínicas, médicos, EPS o IPS "
        "para confirmar existencia, reportes de fraude, venta de incapacidades falsas "
        "o suplantaciones en Colombia. Recibe un texto de búsqueda como input."
    )

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS

            # Realizar múltiples búsquedas especializadas
            searches = [
                (query + " Colombia fraude incapacidad", "Fraude General"),
                (query + " Colombia incapacidad falsa venta", "Venta Incapacidades"),
                (query + " Colombia clinica fachada suplantacion", "Suplantación Entidad"),
            ]

            all_results = []
            seen_urls = set()

            for search_query, category in searches:
                try:
                    results = DDGS().text(search_query, max_results=3)
                    if results:
                        for r in results:
                            url = r.get("href", "")
                            if url not in seen_urls:
                                seen_urls.add(url)
                                all_results.append(
                                    f"[{category}]\n"
                                    f"  Título: {r.get('title', 'Sin título')}\n"
                                    f"  Resumen: {r.get('body', 'Sin contenido')}\n"
                                    f"  URL: {url}"
                                )
                except Exception:
                    continue

            if not all_results:
                return (
                    "No se encontraron resultados relevantes en la web para: "
                    f"'{query}'. Esto puede significar que la entidad/persona NO tiene "
                    "reportes de fraude previos, o que no aparece en fuentes públicas indexadas."
                )

            header = f"=== Resultados OSINT para: '{query}' ===\n\n"
            return header + "\n\n".join(all_results)

        except ImportError:
            return (
                "Error: módulo 'duckduckgo-search' no instalado. "
                "Instalar con: pip install duckduckgo-search. "
                "Sin esta herramienta, no se pueden verificar reportes de fraude web."
            )
        except Exception as e:
            return f"Error en búsqueda OSINT: {e}. Continúa el análisis sin esta verificación."
