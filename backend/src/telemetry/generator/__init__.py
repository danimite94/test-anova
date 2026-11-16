"""Synthetic data generator (PRD FR-001, SPEC §3)."""

from telemetry.generator.core import GENERATOR_VERSION, Dataset, generate
from telemetry.generator.files import write_dataset

__all__ = ["GENERATOR_VERSION", "Dataset", "generate", "write_dataset"]
