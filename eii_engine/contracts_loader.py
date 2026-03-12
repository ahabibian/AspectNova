from pathlib import Path
import json
import yaml

from shared.contract_root import (
    get_contract_root,
    get_schema_path,
    get_contract_registry_file,
)


class ContractLoader:

    def __init__(self):
        self.root = get_contract_root()

    # ---------- Registry ----------

    def load_stage_registry(self, version: str = "v2"):
        registry = get_contract_registry_file(version)

        if not registry.exists():
            raise RuntimeError(f"Stage registry not found: {registry}")

        with registry.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ---------- Generic Schema ----------

    def load_schema(self, *parts: str):
        path = get_schema_path(*parts)

        if not path.exists():
            raise RuntimeError(f"Schema not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ---------- Known Schemas ----------

    def load_cleanup_targets_schema(self):
        return self.load_schema("cleanup_targets.v1.schema.json")

    def load_execution_plan_schema(self):
        return self.load_schema("execution_plan.v1_1.schema.json")

    def load_event_schema(self):
        return self.load_schema("event.v1.schema.json")

    def load_scan_schema(self, name: str):
        return self.load_schema("scan", name)

    # ---------- Debug ----------

    def debug_contract_root(self):
        return str(self.root)