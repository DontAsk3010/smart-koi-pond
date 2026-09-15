from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from smart_koi_pond.digital_twin.koi_stock import FeedingPolicy, KoiStockProfile
from smart_koi_pond.digital_twin.water_exchange import WaterExchangePondModel


class KoiStockWaterExchangePondModel(WaterExchangePondModel):
    """Water-exchange pond model with governed koi-stock derived biological load.

    Koi stock and feeding policy are optional. When both are configured and resolvable,
    their derived biomass/feed values take precedence over legacy direct Pond Profile
    biomass/feed fields. Missing or out-of-domain inputs remain INPUT_REQUIRED.
    """

    def __init__(
        self,
        *args: Any,
        koi_stock: KoiStockProfile | None = None,
        feeding_policy: FeedingPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.koi_stock = koi_stock
        self.feeding_policy = feeding_policy
        self._water_quality_feed_inhibited = False
        self._water_quality_feed_inhibit_reason: str | None = None

    def configure_koi_stock_profile(self, profile: KoiStockProfile) -> None:
        self.koi_stock = profile

    def configure_feeding_policy(self, policy: FeedingPolicy) -> None:
        self.feeding_policy = policy

    def set_water_quality_feed_inhibited(
        self,
        inhibited: bool,
        reason: str | None = None,
    ) -> None:
        self._water_quality_feed_inhibited = bool(inhibited)
        self._water_quality_feed_inhibit_reason = reason if inhibited else None

    def koi_stock_snapshot(self) -> dict[str, Any]:
        if self.koi_stock is None:
            return {
                "configured": False,
                "status": "INPUT_REQUIRED",
                "biomass_kg": None,
                "provenance": "UNAVAILABLE",
            }
        return self.koi_stock.evaluate_biomass()

    def feeding_plan_snapshot(self) -> dict[str, Any]:
        if self.feeding_policy is None:
            return {
                "configured": False,
                "status": "INPUT_REQUIRED",
                "planned_feed_kg_per_day": None,
                "planned_feed_per_meal_g": None,
                "provenance": "UNAVAILABLE",
                "water_quality_feed_inhibited": self._water_quality_feed_inhibited,
                "water_quality_feed_inhibit_reason": (
                    self._water_quality_feed_inhibit_reason
                ),
            }
        plan = self.feeding_policy.evaluate(
            biomass_snapshot=self.koi_stock_snapshot(),
            temperature_c=self.state.temperature_c,
        )
        plan = dict(plan)
        plan["water_quality_feed_inhibited"] = self._water_quality_feed_inhibited
        plan["water_quality_feed_inhibit_reason"] = (
            self._water_quality_feed_inhibit_reason
        )
        planned = plan.get("planned_feed_kg_per_day")
        plan["effective_feed_kg_per_day"] = (
            0.0
            if self._water_quality_feed_inhibited and planned is not None
            else planned
        )
        return plan

    def _effective_biological_load(self) -> tuple[float | None, float | None, str]:
        stock = self.koi_stock_snapshot()
        plan = self.feeding_plan_snapshot()
        if self.koi_stock is not None or self.feeding_policy is not None:
            biomass = stock.get("biomass_kg")
            feed = plan.get("effective_feed_kg_per_day")
            if biomass is None or feed is None:
                return None, None, "KOI_STOCK_OR_FEEDING_INPUT_REQUIRED"
            return float(biomass), float(feed), "KOI_STOCK_DERIVED"
        if self.hydraulics is None:
            return None, None, "POND_PROFILE_INPUT_REQUIRED"
        profile = self.hydraulics.profile
        feed = profile.feed_kg_per_day
        if self._water_quality_feed_inhibited and feed is not None:
            feed = 0.0
        return profile.biomass_kg, feed, "LEGACY_POND_PROFILE"

    def biological_snapshot(self) -> dict[str, Any]:
        snapshot = dict(super().biological_snapshot())
        biomass, feed, load_basis = self._effective_biological_load()
        snapshot["koi_stock"] = self.koi_stock_snapshot()
        snapshot["feeding_plan"] = self.feeding_plan_snapshot()
        snapshot["load_basis"] = load_basis
        snapshot["effective_biomass_kg"] = biomass
        snapshot["effective_feed_kg_per_day"] = feed
        snapshot["feed_inhibited"] = self._water_quality_feed_inhibited
        snapshot["feed_inhibit_reason"] = self._water_quality_feed_inhibit_reason
        return snapshot

    def _biological_oxygen_demand(self, seconds: float) -> float:
        if self.biology is None or self.hydraulics is None:
            return 0.0
        biomass_kg, feed_kg_per_day, _ = self._effective_biological_load()
        actual_volume_l = self.actual_water_volume_l()
        return self.biology.step(
            self.state,
            seconds=seconds,
            volume_l=float(actual_volume_l or 0.0),
            biomass_kg=biomass_kg,
            feed_kg_per_day=feed_kg_per_day,
            circulation_flow_l_min=self.state.circulation_flow_l_min,
            required_circulation_flow_l_min=(
                self.hydraulics.required_circulation_flow_l_min
            ),
        )

    def checkpoint_state(self) -> dict[str, Any]:
        payload = super().checkpoint_state()
        payload["koi_stock_and_feeding"] = {
            "koi_stock": (
                self.koi_stock.to_dict() if self.koi_stock is not None else None
            ),
            "feeding_policy": (
                self.feeding_policy.to_dict()
                if self.feeding_policy is not None
                else None
            ),
            "water_quality_feed_inhibited": self._water_quality_feed_inhibited,
            "water_quality_feed_inhibit_reason": (
                self._water_quality_feed_inhibit_reason
            ),
        }
        return payload

    def restore_engineering_state(self, state: Mapping[str, Any] | None) -> None:
        super().restore_engineering_state(state)
        extra = state.get("koi_stock_and_feeding") if state else None
        if not extra:
            self.koi_stock = None
            self.feeding_policy = None
            self._water_quality_feed_inhibited = False
            self._water_quality_feed_inhibit_reason = None
            return
        stock = extra.get("koi_stock")
        feeding = extra.get("feeding_policy")
        self.koi_stock = KoiStockProfile.from_dict(stock) if stock else None
        self.feeding_policy = FeedingPolicy.from_dict(feeding) if feeding else None
        self._water_quality_feed_inhibited = bool(
            extra.get("water_quality_feed_inhibited", False)
        )
        self._water_quality_feed_inhibit_reason = extra.get(
            "water_quality_feed_inhibit_reason"
        )
