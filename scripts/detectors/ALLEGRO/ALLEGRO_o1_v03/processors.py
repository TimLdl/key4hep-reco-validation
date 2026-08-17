from collections import Counter
import math

from detectors.k4_reco_val_utils.context import EventContext
from detectors.k4_reco_val_utils.helpers import (
    calculate_track_momentum,
    get_collection_hits,
)


def process_silicon_occupancy(ctx: EventContext, data_registry: dict) -> None:
    """Accumulates hit occupancies for Vertex and Silicon Wrapper detectors."""
    if not ctx.is_accepted_eta:
        return

    collections_cfg = ctx.config.get("collections", {})

    if "vtx_digi_hits_per_event" in data_registry:
        vtx_hits = get_collection_hits(ctx.event_data, collections_cfg, "vtx_digis")
        data_registry["vtx_digi_hits_per_event"].append(len(vtx_hits))

    if "siwr_digi_hits_per_event" in data_registry:
        siwr_hits = get_collection_hits(
            ctx.event_data, collections_cfg, "si_wrapper_digis"
        )
        data_registry["siwr_digi_hits_per_event"].append(len(siwr_hits))


def process_drift_chamber(ctx: EventContext, data_registry: dict) -> None:
    """Extracts Drift Chamber total hits, layer hit distributions, and dN/dx PID measurements."""
    subdetectors_cfg = ctx.config.get("subdetectors", {})
    dch_cfg = subdetectors_cfg.get("drift_chamber", {})
    collections_cfg = ctx.config.get("collections", {})

    if ctx.is_accepted_eta:
        dch_digis = get_collection_hits(ctx.event_data, collections_cfg, "dch_digis")

        if "dch_total_hits" in data_registry:
            data_registry["dch_total_hits"].append(len(dch_digis))

        if "drift_chamber_hits_per_layer" in data_registry:
            total_layers = dch_cfg.get("total_layers", 112)
            superlayer_bit_name = dch_cfg.get("superlayer_bit_name", "superlayer")
            layer_bit_name = dch_cfg.get("layer_bit_name", "layer")

            layer_hits = Counter()
            if ctx.bitfield_decoder:
                for hit in dch_digis:
                    cell_id = hit.getCellID()
                    idx = ctx.bitfield_decoder.get(
                        cell_id, superlayer_bit_name
                    ) * 8 + ctx.bitfield_decoder.get(cell_id, layer_bit_name)
                    layer_hits[idx] += 1

            # Fixed layer index alignment across range(0, total_layers)
            data_registry["drift_chamber_hits_per_layer"].extend(
                [layer_hits[idx] for idx in range(total_layers)]
            )

    if "dch_dndx_value" in data_registry:
        for dqdx in get_collection_hits(ctx.event_data, collections_cfg, "dch_dndx"):
            raw_dqdx = dqdx.getDQdx()
            val = getattr(raw_dqdx, "value", raw_dqdx)
            # Filter out uncalculated / failed track sentinel values (-999.0)
            if val is not None and float(val) > 0:
                data_registry["dch_dndx_value"].append(float(val))


def process_topoclusters(ctx: EventContext, data_registry: dict) -> None:
    """Calculates topocluster multiplicities and leading cluster truth response."""
    collections_cfg = ctx.config.get("collections", {})
    topocluster_hits = get_collection_hits(
        ctx.event_data, collections_cfg, "topoclusters"
    )

    if "topocluster_count" in data_registry:
        data_registry["topocluster_count"].append(len(topocluster_hits))

    if (
        topocluster_hits
        and ctx.true_mc_energy > 0
        and "topocluster_truth_response" in data_registry
    ):
        leading_E = max(c.getEnergy() for c in topocluster_hits)
        data_registry["topocluster_truth_response"].append(
            leading_E / ctx.true_mc_energy
        )


def process_calorimetry(ctx: EventContext, data_registry: dict) -> None:
    """Evaluates LAr ECal and HCal energy response, linearity, and shower containment."""
    collections_cfg = ctx.config.get("collections", {})
    ecal_b = get_collection_hits(ctx.event_data, collections_cfg, "ecal_barrel_hits")
    ecal_e = get_collection_hits(ctx.event_data, collections_cfg, "ecal_endcap_hits")
    hcal_e = get_collection_hits(ctx.event_data, collections_cfg, "hcal_endcap_hits")

    if "ecal_cell_hits_per_event" in data_registry:
        data_registry["ecal_cell_hits_per_event"].append(len(ecal_b) + len(ecal_e))

    ecal_b_E = sum(h.getEnergy() for h in ecal_b)
    ecal_e_E = sum(h.getEnergy() for h in ecal_e)
    hcal_e_E = sum(h.getEnergy() for h in hcal_e)

    total_ecal_E = ecal_b_E + ecal_e_E
    total_calo_reco_E = total_ecal_E + hcal_e_E

    if ctx.true_mc_energy > 0 and "total_calo_energy_linearity" in data_registry:
        data_registry["total_calo_energy_linearity"].append(
            total_calo_reco_E / ctx.true_mc_energy
        )

    if total_calo_reco_E > 0 and "ecal_shower_fraction" in data_registry:
        data_registry["ecal_shower_fraction"].append(total_ecal_E / total_calo_reco_E)


def process_track_reconstruction(ctx: EventContext, data_registry: dict) -> None:
    """Computes track hit counts, chi2 quality, impact parameters, and momentum resolution."""
    det_params = ctx.config.get("detector_parameters", {})
    collections_cfg = ctx.config.get("collections", {})
    magnetic_field_tesla = det_params.get("magnetic_field_tesla", 2.0)
    track_collections = collections_cfg.get("track_collections", ["FittedTracks"])

    for col_name in track_collections:
        tracks = ctx.event_data.get(col_name) or []
        valid_tracks = 0

        for track in tracks:
            if track.trackerHits_size() == 0:
                continue
            valid_tracks += 1

            if (
                ctx.is_accepted_eta
                and f"tracker_hits_per_track_{col_name}" in data_registry
            ):
                data_registry[f"tracker_hits_per_track_{col_name}"].append(
                    track.trackerHits_size()
                )

            if track.getNdf() > 0:
                chi2_over_ndf = track.getChi2() / track.getNdf()
                # Ignore failed fits causing severe axis expansion (chi2/ndf > 100)
                if (
                    chi2_over_ndf < 100.0
                    and f"track_fit_chi2_over_ndf_{col_name}" in data_registry
                ):
                    data_registry[f"track_fit_chi2_over_ndf_{col_name}"].append(
                        chi2_over_ndf
                    )

            if track.trackStates_size() > 0:
                st = track.getTrackStates()[0]

                if f"track_impact_parameter_d0_{col_name}" in data_registry:
                    data_registry[f"track_impact_parameter_d0_{col_name}"].append(st.D0)

                p_reco = calculate_track_momentum(st, magnetic_field_tesla)
                if p_reco > 0 and f"momentum_resolution_{col_name}" in data_registry:
                    matched_mc = ctx.track_to_mc_map.get(
                        track.getObjectID(), ctx.primary_mc
                    )
                    if matched_mc:
                        p_mc = matched_mc.getMomentum()
                        p_true = math.hypot(p_mc.x, p_mc.y, p_mc.z)
                        if p_true > 0:
                            data_registry[f"momentum_resolution_{col_name}"].append(
                                (p_reco - p_true) / p_true
                            )

        if f"reconstructed_tracks_per_event_{col_name}" in data_registry:
            data_registry[f"reconstructed_tracks_per_event_{col_name}"].append(
                valid_tracks
            )


def process_track_cluster_matching(ctx: EventContext, data_registry: dict) -> None:
    """Matches tracks to topoclusters using angular proximity to estimate E/p ratios."""
    if "track_ep_ratio" not in data_registry:
        return

    det_params = ctx.config.get("detector_parameters", {})
    collections_cfg = ctx.config.get("collections", {})
    magnetic_field_tesla = det_params.get("magnetic_field_tesla", 2.0)
    track_collections = collections_cfg.get("track_collections", ["FittedTracks"])

    if not track_collections:
        return

    primary_track_col = track_collections[0]
    tracks = ctx.event_data.get(primary_track_col) or []
    topocluster_hits = get_collection_hits(
        ctx.event_data, collections_cfg, "topoclusters"
    )

    for track in tracks:
        if track.trackerHits_size() == 0 or track.trackStates_size() == 0:
            continue

        st = track.getTrackStates()[0]
        p_reco = calculate_track_momentum(st, magnetic_field_tesla)

        if p_reco > 0:
            track_dir_mag = math.sqrt(1.0 + st.tanLambda**2)
            tx = math.cos(st.phi) / track_dir_mag
            ty = math.sin(st.phi) / track_dir_mag
            tz = st.tanLambda / track_dir_mag

            min_delta_r, matched_E = float("inf"), 0.0
            for cluster in topocluster_hits:
                pos = cluster.getPosition()
                pos_mag = math.hypot(pos.x, pos.y, pos.z)
                if pos_mag > 0:
                    cx, cy, cz = pos.x / pos_mag, pos.y / pos_mag, pos.z / pos_mag
                    dot_p = max(-1.0, min(1.0, tx * cx + ty * cy + tz * cz))
                    delta_r = math.acos(dot_p)
                    if delta_r < min_delta_r:
                        min_delta_r = delta_r
                        matched_E = cluster.getEnergy()

            if min_delta_r < 0.2:
                data_registry["track_ep_ratio"].append(matched_E / p_reco)
