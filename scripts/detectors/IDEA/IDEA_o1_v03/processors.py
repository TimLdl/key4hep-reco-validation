from collections import Counter
import math

from detectors.k4_reco_val_utils.context import EventContext
from detectors.k4_reco_val_utils.helpers import (
    calculate_track_momentum,
    get_collection_hits,
)


def process_digi_and_occupancy(ctx: EventContext, data_registry: dict) -> None:
    """Calculates vertex, silicon wrapper, drift chamber, and muon system hit occupancies for IDEA."""
    if not ctx.is_accepted_eta:
        return

    cols = ctx.config.get("collections", {})
    sub_cfg = ctx.config.get("subdetectors", {}).get("drift_chamber", {})

    if "vtx_digi_hits_per_event" in data_registry:
        vtx_hits = get_collection_hits(ctx.event_data, cols, "vtx_digis")
        data_registry["vtx_digi_hits_per_event"].append(len(vtx_hits))

    if "siwr_digi_hits_per_event" in data_registry:
        siwr_hits = get_collection_hits(ctx.event_data, cols, "si_wrapper_digis")
        data_registry["siwr_digi_hits_per_event"].append(len(siwr_hits))

    if "drift_chamber_hits_per_layer" in data_registry:
        layer_hits = Counter()
        dch_digis = get_collection_hits(ctx.event_data, cols, "dch_digis")
        total_layers = sub_cfg.get("total_layers", 112)
        sl_bit = sub_cfg.get("superlayer_bit_name", "superlayer")
        l_bit = sub_cfg.get("layer_bit_name", "layer")

        if ctx.bitfield_decoder:
            for hit in dch_digis:
                cell_id = hit.getCellID()
                idx = ctx.bitfield_decoder.get(
                    cell_id, sl_bit
                ) * 8 + ctx.bitfield_decoder.get(cell_id, l_bit)
                layer_hits[idx] += 1

        data_registry["drift_chamber_hits_per_layer"].extend(
            [0] * (total_layers - len(layer_hits))
        )
        data_registry["drift_chamber_hits_per_layer"].extend(layer_hits.values())

    if "muon_system_hits_per_event" in data_registry:
        muon_hits = get_collection_hits(ctx.event_data, cols, "muon_tracker_hits")
        data_registry["muon_system_hits_per_event"].append(len(muon_hits))


def process_drift_chamber_dndx(ctx: EventContext, data_registry: dict) -> None:
    """Extracts drift chamber dN/dx PID charge deposition values."""
    if "dch_dndx_value" not in data_registry:
        return

    cols = ctx.config.get("collections", {})
    for dqdx in get_collection_hits(ctx.event_data, cols, "dch_dndx"):
        val = dqdx.getDQdx().value if hasattr(dqdx, "getDQdx") else None
        if val is not None:
            data_registry["dch_dndx_value"].append(val)


def process_tracking_performance(ctx: EventContext, data_registry: dict) -> None:
    """Calculates track multiplicity, hit counts, fit chi2/ndf, and momentum resolution."""
    cols = ctx.config.get("collections", {})
    track_collections = cols.get("track_collections", ["FittedTracks"])
    b_field = ctx.config.get("detector_parameters", {}).get("magnetic_field_tesla", 2.0)

    for col_name in track_collections:
        tracks = ctx.event_data.get(col_name) or []
        valid_tracks = 0
        hits_key = f"tracker_hits_per_track_{col_name}"
        chi2_key = f"track_fit_chi2_over_ndf_{col_name}"
        p_res_key = f"momentum_resolution_{col_name}"
        reco_key = f"reconstructed_tracks_per_event_{col_name}"

        for t in tracks:
            if t.trackerHits_size() == 0:
                continue
            valid_tracks += 1

            if ctx.is_accepted_eta and hits_key in data_registry:
                data_registry[hits_key].append(t.trackerHits_size())

            if t.getNdf() > 0 and chi2_key in data_registry:
                data_registry[chi2_key].append(t.getChi2() / t.getNdf())

            if t.trackStates_size() > 0 and p_res_key in data_registry:
                st = t.getTrackStates()[0]
                p_reco = calculate_track_momentum(st, b_field)
                if p_reco > 0:
                    matched_mc = ctx.track_to_mc_map.get(
                        t.getObjectID(), ctx.primary_mc
                    )
                    if matched_mc:
                        p_mc = matched_mc.getMomentum()
                        p_true = math.sqrt(p_mc.x**2 + p_mc.y**2 + p_mc.z**2)
                        if p_true > 0:
                            data_registry[p_res_key].append((p_reco - p_true) / p_true)

        if reco_key in data_registry:
            data_registry[reco_key].append(valid_tracks)


def process_dual_readout_calorimetry(ctx: EventContext, data_registry: dict) -> None:
    """Computes Cherenkov/Scintillation linearity and C/S response ratio."""
    cols = ctx.config.get("collections", {})
    c_hits = get_collection_hits(ctx.event_data, cols, "calo_cherenkov")
    s_hits = get_collection_hits(ctx.event_data, cols, "calo_scintillation")
    e_c = sum(h.getEnergy() for h in c_hits)
    e_s = sum(h.getEnergy() for h in s_hits)

    if ctx.true_mc_energy > 0:
        if "calorimeter_linearity_cherenkov" in data_registry:
            data_registry["calorimeter_linearity_cherenkov"].append(
                e_c / ctx.true_mc_energy
            )
        if "calorimeter_linearity_scintillation" in data_registry:
            data_registry["calorimeter_linearity_scintillation"].append(
                e_s / ctx.true_mc_energy
            )
        if e_s > 0 and "calorimeter_c_over_s_ratio" in data_registry:
            data_registry["calorimeter_c_over_s_ratio"].append(e_c / e_s)


def process_topoclusters(ctx: EventContext, data_registry: dict) -> None:
    """Calculates topocluster count and leading cluster energy."""
    cols = ctx.config.get("collections", {})
    topos = get_collection_hits(ctx.event_data, cols, "topoclusters")

    if "topocluster_count" in data_registry:
        data_registry["topocluster_count"].append(len(topos))

    if topos and "topocluster_leading_energy" in data_registry:
        data_registry["topocluster_leading_energy"].append(
            max(c.getEnergy() for c in topos)
        )


IDEA_PROCESSORS = [
    process_digi_and_occupancy,
    process_drift_chamber_dndx,
    process_tracking_performance,
    process_dual_readout_calorimetry,
    process_topoclusters,
]
