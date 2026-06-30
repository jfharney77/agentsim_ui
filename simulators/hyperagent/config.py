"""
Centralized configuration for the HyperAgent simulation.

Based on the HyperAgent architecture from FSoft-AI4Code:
https://github.com/FSoft-AI4Code/HyperAgent
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict


def _default_model() -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    defaults = {
        "anthropic": "claude-sonnet-4-5-20250929",
        "openai": "gpt-4o",
    }
    return (
        os.getenv("HYPERAGENT_MODEL")
        or os.getenv("ORCHESTRATOR_MODEL")
        or os.getenv("SWARM_MODEL")
        or defaults.get(provider, "gpt-4o")
    )


@dataclass
class AgentConfig:
    """Configuration for an individual agent."""
    model: str = field(default_factory=_default_model)
    temperature: float = 0.2
    max_tokens: int = 4096
    max_retries: int = 3
    timeout_seconds: int = 120


@dataclass
class SimulationConfig:
    """
    Top-level configuration for the HyperAgent simulation.

    Based on HyperAgent's multi-agent architecture with:
    - Planner: Central decision-making unit
    - Navigator: Information retrieval specialist
    - Editor: Code modification and generation
    - Executor: Solution validation and issue reproduction
    """

    repo_url: str = ""
    commit: str = "main"
    language: str = "python"
    clone_dir: str = "data/repos"
    mode: str = "patch"

    planner: AgentConfig = field(default_factory=lambda: AgentConfig(
        model=_default_model(),
        temperature=0.2,
    ))
    navigator: AgentConfig = field(default_factory=lambda: AgentConfig(
        model=_default_model(),
        temperature=0.1,
    ))
    editor: AgentConfig = field(default_factory=lambda: AgentConfig(
        model=_default_model(),
        temperature=0.2,
    ))
    executor: AgentConfig = field(default_factory=lambda: AgentConfig(
        model=_default_model(),
        temperature=0.1,
    ))

    max_iterations: int = 10
    verbose: bool = True
    log_file: Optional[str] = "hyperagent_simulation.log"
    enable_llm: bool = True
    simulation_mode: bool = False

    @classmethod
    def from_dict(cls, config_dict: Dict) -> "SimulationConfig":
        agent_fields = ["planner", "navigator", "editor", "executor"]
        for field_name in agent_fields:
            if field_name in config_dict and isinstance(config_dict[field_name], dict):
                config_dict[field_name] = AgentConfig(**config_dict[field_name])
        return cls(**config_dict)

    @classmethod
    def from_env(cls) -> "SimulationConfig":
        return cls(
            repo_url=os.getenv("HYPERAGENT_REPO_URL", ""),
            commit=os.getenv("HYPERAGENT_COMMIT", "main"),
            language=os.getenv("HYPERAGENT_LANGUAGE", "python"),
            verbose=os.getenv("HYPERAGENT_VERBOSE", "true").lower() == "true",
            simulation_mode=os.getenv("HYPERAGENT_SIMULATION_MODE", "false").lower() == "true",
        )
