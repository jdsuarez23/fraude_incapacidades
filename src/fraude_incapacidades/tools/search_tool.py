from __future__ import annotations

from crewai.tools import BaseTool


class OSINTSearchTool(BaseTool):
    name: str = "Busqueda Web OSINT"
    description: str = (
        "Busca en la web (DuckDuckGo) información ESPECÍFICA sobre una clínica, "
        "médico, EPS o IPS para confirmar existencia o encontrar reportes de fraude "
        "específicos contra esa entidad en Colombia. Recibe el nombre a buscar."
    )

    def _run(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS

            # Búsqueda más neutral: primero verificar existencia, luego fraude específico
            searches = [
                (query + " Colombia clinica hospital IPS", "Existencia Entidad"),
                (f'"{query}" Colombia fraude incapacidad falsa denunciado', "Fraude Específico"),
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
                                title = r.get("title", "Sin título")
                                body = r.get("body", "Sin contenido")
                                
                                # Filter: only flag as fraud if the specific entity name appears
                                # in the result alongside fraud-related terms
                                query_lower = query.lower().strip()
                                combined = (title + " " + body).lower()
                                is_specific = query_lower in combined
                                
                                if category == "Fraude Específico" and not is_specific:
                                    category = "Resultado Genérico (NO específico de esta entidad)"
                                
                                all_results.append(
                                    f"[{category}]\n"
                                    f"  Título: {title}\n"
                                    f"  Resumen: {body}\n"
                                    f"  URL: {url}"
                                )
                except Exception:
                    continue

            if not all_results:
                return (
                    f"No se encontraron resultados para '{query}' en la web. "
                    "Esto NO es evidencia de fraude. Muchas clínicas pequeñas o "
                    "consultorios no tienen presencia web significativa."
                )

            header = f"=== Resultados OSINT para: '{query}' ===\n"
            header += "NOTA: Solo los resultados marcados como 'Fraude Específico' que mencionan directamente esta entidad son relevantes.\n\n"
            return header + "\n\n".join(all_results)

        except ImportError:
            return (
                "Módulo de búsqueda web no disponible. "
                "Esto NO afecta la validez del documento."
            )
        except Exception as e:
            return f"Error en búsqueda OSINT: {e}. Esto NO es evidencia de fraude."
