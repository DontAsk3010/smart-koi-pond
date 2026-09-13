"""Capability-based modular platform registry and baseline evaluation."""

from .registry import (
    DEFAULT_MODULE_MANIFESTS,
    DEFAULT_SIMULATION_BASELINE,
    CapabilityRegistry,
    ModuleManifest,
)

__all__ = [
    "CapabilityRegistry",
    "DEFAULT_MODULE_MANIFESTS",
    "DEFAULT_SIMULATION_BASELINE",
    "ModuleManifest",
]
