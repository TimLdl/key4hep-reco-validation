"""Per-event context dataclass and builder.

The :class:`EventContext` holds all per-event invariants that processors need,
extracted once at the start of each event to avoid redundant lookups.

Building a context may return ``None`` if no primary generator particle is
found in the event (the engine skips such events).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging


@dataclass
class EventContext:
    event_data: Dict[str, Any]
    primary_mc: Optional[Any]
    true_mc_energy: float
    is_accepted_eta: bool
    track_to_mc_map: Dict[Any, Any]
    config: Dict[str, Any]
    bitfield_decoder: Any


def build_event_context(
    event_data: Dict[str, Any],
    config: Dict[str, Any],
    bitfield_decoder: Any = None,
    max_eta: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[EventContext]:
    """Extracts per-event invariants and constructs an EventContext object."""
    from detectors.k4_reco_val_utils.helpers import (
        evaluate_particle_eta_acceptance,
        extract_track_to_mc_map,
    )

    collections_config = config.get("collections", {})
    mc_particle_collection = collections_config.get("mc_particles", "MCParticles")
    mc_particles = event_data.get(mc_particle_collection) or []

    primary_mc = next((p for p in mc_particles if p.getGeneratorStatus() == 1), None)
    if not primary_mc:
        return None

    true_mc_energy = primary_mc.getEnergy()
    is_accepted_eta, _ = evaluate_particle_eta_acceptance(primary_mc, max_eta)

    association_collection = collections_config.get(
        "track_mc_assoc", "TracksFromGenParticlesAssociation"
    )
    track_to_mc_map = extract_track_to_mc_map(
        event_data.get(association_collection), logger
    )

    return EventContext(
        event_data=event_data,
        primary_mc=primary_mc,
        true_mc_energy=true_mc_energy,
        is_accepted_eta=is_accepted_eta,
        track_to_mc_map=track_to_mc_map,
        config=config,
        bitfield_decoder=bitfield_decoder,
    )
