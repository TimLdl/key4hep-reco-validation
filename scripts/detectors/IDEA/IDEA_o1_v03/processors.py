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

    sub_cfg = ctx.config.get("subdetectors", {}).get("drift_chamber", {})

    if (
        "vtx_digi_hits_per_event" in data_registry
        or "vtx_hits_per_layer" in data_registry
    ):
        vtx_hits = get_collection_hits(ctx, "vtx_digis")

        if "vtx_digi_hits_per_event" in data_registry:
            data_registry["vtx_digi_hits_per_event"].append(len(vtx_hits))

        if "vtx_hits_per_layer" in data_registry:
            vtx_layer_hits = Counter()
            if ctx.bitfield_decoder:
                for hit in vtx_hits:
                    layer = ctx.bitfield_decoder.get(hit.getCellID(), "layer")
                    vtx_layer_hits[layer] += 1
            data_registry["vtx_hits_per_layer"].extend(vtx_layer_hits.values())

    if "siwr_digi_hits_per_event" in data_registry:
        siwr_hits = get_collection_hits(ctx, "si_wrapper_digis")
        data_registry["siwr_digi_hits_per_event"].append(len(siwr_hits))

    if "drift_chamber_hits_per_layer" in data_registry:
        layer_hits = Counter()
        dch_digis = get_collection_hits(ctx, "dch_digis")
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

        # Correctly preserve exact layer index alignment (0 to total_layers - 1)
        data_registry["drift_chamber_hits_per_layer"].extend(
            layer_hits[idx] for idx in range(total_layers)
        )

    if "muon_system_hits_per_event" in data_registry:
        muon_hits = get_collection_hits(ctx, "muon_tracker_hits")
        data_registry["muon_system_hits_per_event"].append(len(muon_hits))


def process_drift_chamber_dndx(ctx: EventContext, data_registry: dict) -> None:
    """TODO"""
    if "dch_dndx_value" not in data_registry:
        return

    dndx_hits = get_collection_hits(ctx, "dch_dndx")

    for item in dndx_hits:
        val = item.getNCluster()
        if val > 0:
            data_registry["dch_dndx_value"].append(float(val))


def process_tracking_performance(ctx: EventContext, data_registry: dict) -> None:
    """Calculates track multiplicity, hit counts, fit chi2/ndf, and momentum resolution."""
    cols = ctx.config.get("collections", {})
    track_collections = cols.get("track_collections", ["FittedTracks"])
    b_field = ctx.config.get("detector_parameters", {}).get("magnetic_field_tesla", 2.0)

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
                        p_true = math.hypot(p_mc.x, p_mc.y, p_mc.z)
                        if p_true > 0:
                            data_registry[p_res_key].append((p_reco - p_true) / p_true)

        if reco_key in data_registry:
            data_registry[reco_key].append(valid_tracks)


def process_dual_readout_calorimetry(ctx: EventContext, data_registry: dict) -> None:
    """Computes Cherenkov and Scintillation energy linearities."""
    c_hits = get_collection_hits(ctx, "calo_cherenkov")
    s_hits = get_collection_hits(ctx, "calo_scintillation")

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


def process_topoclusters(ctx: EventContext, data_registry: dict) -> None:
    """Calculates topocluster count, leading energy, and angular resolution (Delta phi, Delta theta)."""
    topos = get_collection_hits(ctx, "topoclusters")

    if "topocluster_count" in data_registry:
        data_registry["topocluster_count"].append(len(topos))

    if "topocluster_leading_energy" in data_registry:
        leading_e = max((c.getEnergy() for c in topos), default=0.0)
        data_registry["topocluster_leading_energy"].append(leading_e)

    if (
        "topocluster_delta_phi" in data_registry
        or "topocluster_delta_theta" in data_registry
    ) and ctx.primary_mc:
        mc_p = ctx.primary_mc.getMomentum()
        p_mag = math.hypot(mc_p.x, mc_p.y, mc_p.z)
        if p_mag > 0:
            mc_phi = math.atan2(mc_p.y, mc_p.x)
            mc_theta = math.acos(mc_p.z / p_mag)

            for c in topos:
                pos = c.getPosition()
                r_mag = math.hypot(pos.x, pos.y, pos.z)
                if r_mag > 0:
                    cl_phi = math.atan2(pos.y, pos.x)
                    cl_theta = math.acos(pos.z / r_mag)

                    d_phi = cl_phi - mc_phi
                    d_phi = (d_phi + math.pi) % (2 * math.pi) - math.pi
                    d_theta = cl_theta - mc_theta

                    if "topocluster_delta_phi" in data_registry:
                        data_registry["topocluster_delta_phi"].append(d_phi)
                    if "topocluster_delta_theta" in data_registry:
                        data_registry["topocluster_delta_theta"].append(d_theta)
