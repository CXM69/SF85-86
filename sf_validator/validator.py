"""Top-level suite runner for the SF-85/SF-86 validator."""

from __future__ import annotations

from typing import Any, Dict, List

from .ever_flags import EverFlagScanner
from .flag_generator import FlagGenerator
from .gap_engine import GapEngine
from .models import ValidationFlag
from .section_11 import Section11Validator
from .section_13 import Section13Validator


class ValidatorSuite:
    def __init__(self) -> None:
        self.gap_engine = GapEngine()
        self.section_11 = Section11Validator()
        self.section_13 = Section13Validator()
        self.flag_generator = FlagGenerator()
        self.ever_flags = EverFlagScanner()

    def run(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        flags: List[ValidationFlag] = []
        flags.extend(self.gap_engine.generate(payload))
        flags.extend(self.section_11.generate(payload))
        flags.extend(self.section_13.generate(payload))
        flags.extend(self.flag_generator.generate(payload))
        flags.extend(self.ever_flags.generate(payload))
        return flags
