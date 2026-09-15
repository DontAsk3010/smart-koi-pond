from __future__ import annotations

import math
from dataclasses import dataclass


UNIONIZED_AMMONIA_N_PARAMETER = "unionized_ammonia_n_mg_l"
UNIONIZED_AMMONIA_FORMULA_ID = "EPA_EMERSON_FRESHWATER_NH3_FRACTION_V1"
UNIONIZED_AMMONIA_SOURCE_REFERENCE = (
    "US EPA 822-R-98-008, 1998 Update of Ambient Water Quality Criteria for "
    "Ammonia; Emerson et al. (1975) freshwater speciation equation"
)


@dataclass(slots=True, frozen=True)
class UnionizedAmmoniaResult:
    tan_n_mg_l: float
    ph: float
    temperature_c: float
    pka: float
    unionized_fraction: float
    unionized_ammonia_n_mg_l: float
    formula_id: str = UNIONIZED_AMMONIA_FORMULA_ID
    source_reference: str = UNIONIZED_AMMONIA_SOURCE_REFERENCE
    provenance: str = "CALCULATED"
    basis: str = "VALIDATED_TAN_N_PLUS_PH_PLUS_TEMPERATURE"

    def to_dict(self) -> dict[str, float | str]:
        return {
            "tan_n_mg_l": self.tan_n_mg_l,
            "ph": self.ph,
            "temperature_c": self.temperature_c,
            "pka": self.pka,
            "unionized_fraction": self.unionized_fraction,
            "unionized_ammonia_n_mg_l": self.unionized_ammonia_n_mg_l,
            "formula_id": self.formula_id,
            "source_reference": self.source_reference,
            "provenance": self.provenance,
            "basis": self.basis,
        }


def calculate_unionized_ammonia_n(
    *,
    tan_n_mg_l: float,
    ph: float,
    temperature_c: float,
) -> UnionizedAmmoniaResult:
    """Calculate un-ionized ammonia as nitrogen (NH3-N) for freshwater.

    TAN is supplied as mg N/L, so the returned NH3 value is also mg N/L. This is
    speciation, not a new measured sensor value and not a biological threshold.
    """
    tan = float(tan_n_mg_l)
    ph_value = float(ph)
    temperature = float(temperature_c)
    if not all(math.isfinite(value) for value in (tan, ph_value, temperature)):
        raise ValueError("TAN, pH, and temperature must be finite")
    if tan < 0:
        raise ValueError("TAN must be non-negative")
    if not 0.0 <= ph_value <= 14.0:
        raise ValueError("pH must be between 0 and 14")
    if temperature <= -273.2:
        raise ValueError("temperature is outside the formula domain")

    pka = 0.09018 + 2729.92 / (273.2 + temperature)
    fraction = 1.0 / (1.0 + 10.0 ** (pka - ph_value))
    return UnionizedAmmoniaResult(
        tan_n_mg_l=tan,
        ph=ph_value,
        temperature_c=temperature,
        pka=pka,
        unionized_fraction=fraction,
        unionized_ammonia_n_mg_l=tan * fraction,
    )
