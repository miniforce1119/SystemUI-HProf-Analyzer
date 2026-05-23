"""
Local config 로더.

config/local.yaml을 읽어 dataclass로 노출.
없으면 명확한 에러 메시지로 셋업 절차 안내.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "local.yaml"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "local.example.yaml"


class ConfigError(RuntimeError):
    pass


@dataclass
class Paths:
    adb: str = ""
    hprof_conv: str = ""
    mat_parse_heap_dump: str = ""
    java: str = ""
    work_dir: str = ""
    samples_dir: str = ""


@dataclass
class MatConfig:
    memory_flag: str = "-Xmx6g"
    timeout_seconds: int = 600
    output_format_preference: list[str] = field(default_factory=lambda: ["csv", "html", "txt"])


@dataclass
class LlmConfig:
    provider: str = "anthropic"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RagConfig:
    backend: str = "chroma"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MailConfig:
    enabled: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    environment: str = "unknown"
    paths: Paths = field(default_factory=Paths)
    mat: MatConfig = field(default_factory=MatConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    rag: RagConfig = field(default_factory=RagConfig)
    mail: MailConfig = field(default_factory=MailConfig)
    source_path: str = ""


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not cfg_path.exists():
        raise ConfigError(
            f"config/local.yaml not found at: {cfg_path}\n"
            f"\n"
            f"새 PC 셋업 절차:\n"
            f"  1. cp {EXAMPLE_CONFIG_PATH.relative_to(PROJECT_ROOT)} "
            f"{cfg_path.relative_to(PROJECT_ROOT)}\n"
            f"  2. local.yaml의 paths 항목을 이 PC의 실제 경로로 채워 넣으세요.\n"
            f"  3. python -m systemui_hprof_analyzer env-check"
        )

    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return _from_dict(raw, source=str(cfg_path))


def _from_dict(raw: dict[str, Any], source: str) -> Config:
    paths_raw = raw.get("paths") or {}
    mat_raw = raw.get("mat") or {}
    llm_raw = raw.get("llm") or {}
    rag_raw = raw.get("rag") or {}
    mail_raw = raw.get("mail") or {}

    return Config(
        environment=str(raw.get("environment", "unknown")),
        paths=Paths(
            adb=str(paths_raw.get("adb", "")),
            hprof_conv=str(paths_raw.get("hprof_conv", "")),
            mat_parse_heap_dump=str(paths_raw.get("mat_parse_heap_dump", "")),
            java=str(paths_raw.get("java", "")),
            work_dir=str(paths_raw.get("work_dir", "")),
            samples_dir=str(paths_raw.get("samples_dir", "")),
        ),
        mat=MatConfig(
            memory_flag=str(mat_raw.get("memory_flag", "-Xmx6g")),
            timeout_seconds=int(mat_raw.get("timeout_seconds", 600)),
            output_format_preference=list(
                mat_raw.get("output_format_preference") or ["csv", "html", "txt"]
            ),
        ),
        llm=LlmConfig(
            provider=str(llm_raw.get("provider", "anthropic")),
            raw=llm_raw,
        ),
        rag=RagConfig(
            backend=str(rag_raw.get("backend", "chroma")),
            raw=rag_raw,
        ),
        mail=MailConfig(
            enabled=bool(mail_raw.get("enabled", False)),
            raw=mail_raw,
        ),
        source_path=source,
    )
