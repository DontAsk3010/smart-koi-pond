from smart_koi_pond.dashboard.service import RuntimeApplicationService


class SourceWaterQualifiedRuntimeApplicationService(RuntimeApplicationService):
    """Application boundary for the source-water qualification contract.

    Command handling remains inherited from the canonical application service; only
    the published source-water exchange schema marker is advanced to match the model.
    """

    def publication(self, *, after_sequence: int = 0):
        publication = super().publication(after_sequence=after_sequence)
        publication["source_water_exchange_schema_version"] = 2
        return publication
