from abc import ABC, abstractmethod
from pathlib import Path

class Stage(ABC):
    name: str
    version: str

    @abstractmethod
    def run(self, input_path: Path, output_dir: Path, run_id: str):
        pass
