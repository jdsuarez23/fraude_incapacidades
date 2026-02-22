from __future__ import annotations

from pathlib import Path
from typing import Dict

from crewai import Agent, Task, Crew, Process

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Falta la dependencia PyYAML para cargar configuraciones YAML. "
        "Instala con: pip install PyYAML"
    ) from e

from crewai_tools import OCRTool


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Rutas a los YAML de configuración
_BASE = Path(__file__).parent / "config"
_AGENTS_YAML = _BASE / "agents.yaml"
_TASKS_YAML = _BASE / "tasks.yaml"

agents_cfg = _load_yaml(_AGENTS_YAML)
tasks_cfg = _load_yaml(_TASKS_YAML)


def _build_agents(cfg: dict) -> Dict[str, Agent]:
    agents: Dict[str, Agent] = {}
    for name, data in cfg.items():
        tools = []
        if name == "ocr_agent":
            tools = [OCRTool()]
        agents[name] = Agent(
            role=data.get("role", ""),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            tools=tools,
            verbose=True,
        )
    return agents


def _build_tasks(cfg: dict, agents: Dict[str, Agent]) -> Dict[str, Task]:
    tasks: Dict[str, Task] = {}
    for name, data in cfg.items():
        agent_key = data.get("agent", "")
        agent = agents.get(agent_key)
        if agent is None:
            raise ValueError(f"La tarea '{name}' referencia un agente desconocido: '{agent_key}'")
        tasks[name] = Task(
            description=data.get("description", ""),
            agent=agent,
            expected_output=data.get("expected_output", ""),
        )
    return tasks


_agents = _build_agents(agents_cfg)
_tasks = _build_tasks(tasks_cfg, _agents)


# Orden lógico de ejecución (secuencial)
crew = Crew(
    agents=[
        _agents["ocr_agent"],
        _agents["document_structure_agent"],
        _agents["medical_data_verifier"],
        _agents["fraud_detection_agent"],
        _agents["report_generator_agent"],
    ],
    tasks=[
        _tasks["extract_text_task"],
        _tasks["analyze_structure_task"],
        _tasks["validate_medical_data_task"],
        _tasks["detect_fraud_task"],
        _tasks["generate_report_task"],
    ],
    process=Process.sequential,
)
