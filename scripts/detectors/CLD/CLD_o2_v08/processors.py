"""Detector-specific event metrics for CLD (CLD_o2_v08).

Collection names follow the CLDConfig (https://github.com/key4hep/CLDConfig)
reconstruction chain: `SiTracks_Refitted` for fitted tracks, `MUON` for the
digitised muon-system (yoke) hits, and `PandoraClusters` / `PandoraPFOs` for
the Arbor/PandoraPFA calorimetric reconstruction output.
"""

import math

from detectors.k4_reco_val_utils.context import EventContext
from detectors.k4_reco_val_utils.helpers import (
    calculate_track_momentum,
    get_collection_hits,
)


def process_digi_and_occupancy(ctx: EventContext, data_registry: dict) -> None:
    """Calculates vertex, inner/outer tracker, and muon system hit occupancies for CLD."""
    if not ctx.is_accepted_eta:
        return

    if "vtx_digi_hits_per_event" in data_registry:
        vtx_hits = get_collection_hits(ctx, "vtx_digis")
        data_registry["vtx_digi_hits_per_event"].append(len(vtx_hits))

    if "inner_tracker_digi_hits_per_event" in data_registry:
        inner_hits = get_collection_hits(ctx, "inner_tracker_digis")
        data_registry["inner_tracker_digi_hits_per_event"].append(len(inner_hits))

    if "outer_tracker_digi_hits_per_event" in data_registry:
        outer_hits = get_collection_hits(ctx, "outer_tracker_digis")
        data_registry["outer_tracker_digi_hits_per_event"].append(len(outer_hits))

    if "muon_system_hits_per_event" in data_registry:
        muon_hits = get_collection_hits(ctx, "muon_system_hits")
        data_registry["muon_system_hits_per_event"].append(len(muon_hits))


def process_tracking_performance(ctx: EventContext, data_registry: dict) -> None:
    """Calculates track multiplicity, hit counts, fit chi2/ndf, and momentum resolution."""
    collections_config = ctx.config.get("collections", {})
    track_collections = collections_config.get(
        "track_collections", ["SiTracks_Refitted"]
    )
    magnetic_field_tesla = ctx.config.get("detector_parameters", {}).get(
        "magnetic_field_tesla", 2.0
    )

    for col_name in track_collections:
        try:
            tracks = ctx.event_data.get(col_name) or []
        except (KeyError, RuntimeError):
            tracks = []

        valid_tracks = 0
        hits_key = f"tracker_hits_per_track_{col_name}"
        chi2_key = f"track_fit_chi2_over_ndf_{col_name}"
        p_res_key = f"momentum_resolution_{col_name}"
        reco_key = f"reconstructed_tracks_per_event_{col_name}"

        for track in tracks:
            if track.trackerHits_size() == 0:
                continue
            valid_tracks += 1

            if ctx.is_accepted_eta and hits_key in data_registry:
                data_registry[hits_key].append(track.trackerHits_size())

            if track.getNdf() > 0 and chi2_key in data_registry:
                data_registry[chi2_key].append(track.getChi2() / track.getNdf())

            if track.trackStates_size() > 0 and p_res_key in data_registry:
                track_state = track.getTrackStates()[0]
                reconstructed_momentum = calculate_track_momentum(
                    track_state, magnetic_field_tesla
                )
                if reconstructed_momentum > 0:
                    matched_mc = ctx.track_to_mc_map.get(
                        track.getObjectID(), ctx.primary_mc
                    )
                    if matched_mc:
                        p_mc = matched_mc.getMomentum()
                        p_true = math.hypot(p_mc.x, p_mc.y, p_mc.z)
                        if p_true > 0:
                            data_registry[p_res_key].append(
                                (reconstructed_momentum - p_true) / p_true
                            )

        if reco_key in data_registry:
            data_registry[reco_key].append(valid_tracks)


def process_calorimetry_and_pfo(ctx: EventContext, data_registry: dict) -> None:
    """Computes calorimeter cluster and particle-flow-object multiplicities and linearities."""
    clusters = get_collection_hits(ctx, "calo_clusters")
    pfos = get_collection_hits(ctx, "pfo_particles")

    if "calo_cluster_count" in data_registry:
        data_registry["calo_cluster_count"].append(len(clusters))

    if ctx.true_mc_energy > 0:
        if "calo_cluster_energy_linearity" in data_registry:
            leading_cluster_energy = max(
                (c.getEnergy() for c in clusters), default=0.0
            )
            data_registry["calo_cluster_energy_linearity"].append(
                leading_cluster_energy / ctx.true_mc_energy
            )

        if "pfo_energy_linearity" in data_registry:
            leading_pfo_energy = max((p.getEnergy() for p in pfos), default=0.0)
            data_registry["pfo_energy_linearity"].append(
                leading_pfo_energy / ctx.true_mc_energy
            )
