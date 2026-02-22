from __future__ import annotations

from pathlib import Path
from typing import Dict

import os
from crewai import Agent, Task, Crew, Process, LLM

try:
    import yaml  # type: ignore
except Exception as e:
    raise ImportError("Instala con: pip install PyYAML") from e

from crewai_tools import OCRTool
from .tools.search_tool import OSINTSearchTool

def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

_BASE = Path(__file__).parent / "config"
agents_cfg = _load_yaml(_BASE / "agents.yaml")
tasks_cfg = _load_yaml(_BASE / "tasks.yaml")

def _build_agents(cfg: dict) -> Dict[str, Agent]:
    agents: Dict[str, Agent] = {}
    
    # Init strict LLM to avoid env lookup issues
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    default_llm = LLM(model="gpt-4o", api_key=api_key) if api_key else None
    
    for name, data in cfg.items():
        tools = []
        if name == "auditor_medico_forense":
            tools = [OCRTool()]
        elif name == "investigador_osint":
            tools = [OSINTSearchTool()]
            
        agents[name] = Agent(
            role=data.get("role", ""),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            tools=tools,
            llm=default_llm,
            verbose=False,
            allow_delegation=False
        )
    return agents

def _build_tasks(cfg: dict, agents: Dict[str, Agent]) -> Dict[str, Task]:
    tasks: Dict[str, Task] = {}
    for name, data in cfg.items():
        agent_key = data.get("agent", "")
        agent = agents.get(agent_key)
        if agent is None:
            raise ValueError(f"Tarea '{name}' referencia agente desconocido '{agent_key}'")
        tasks[name] = Task(
            description=data.get("description", ""),
            agent=agent,
            expected_output=data.get("expected_output", ""),
        )
    return tasks

_agents = _build_agents(agents_cfg)
_tasks = _build_tasks(tasks_cfg, _agents)

crew = Crew(
    agents=[
        _agents["auditor_medico_forense"],
        _agents["investigador_osint"],
        _agents["redactor_dictamen"],
    ],
    tasks=[
        _tasks["extract_and_validate_task"],
        _tasks["search_osint_task"],
        _tasks["generate_final_report_task"],
    ],
    process=Process.sequential,
)
