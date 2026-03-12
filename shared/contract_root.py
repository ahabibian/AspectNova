from pathlib import Path
import os


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_contract_root() -> Path:
    env = os.getenv("ASPECTNOVA_CONTRACTS_ROOT")
    if env:
        root = Path(env)
        if root.exists():
            return root

    repo_root = get_repo_root()
    canonical = repo_root / "contracts"
    if canonical.exists():
        return canonical

    legacy = repo_root / "agent" / "contracts"
    if legacy.exists():
        return legacy

    return canonical


def get_contract_registry_file(version: str = "v2") -> Path:
    return get_contract_root() / "registry" / f"stage_contracts.{version}.yml"


def get_schema_path(*parts: str) -> Path:
    return get_contract_root() / "schemas" / Path(*parts)


def get_contract_tool_path(*parts: str) -> Path:
    return get_contract_root() / "tools" / Path(*parts)