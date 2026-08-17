import argparse
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import ROOT
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from detectors.k4_reco_val_utils.helpers import (
    build_and_fill_histograms,
    calculate_track_momentum,
    evaluate_particle_eta_acceptance,
    extract_track_to_mc_map,
    init_bitfield_coder,
    resolve_histogram_definitions,
)

from detectors.k4_reco_val_utils.io import (
    open_podio_root_reader,
    write_histograms_to_file,
)
from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("ALLEGRO_hist")


def analyze_detector_simulation_file(
    podio_reader,
    particle_prefix: str,
    det_cfg: dict,
    bitfield_decoder=None,
    max_pseudorapidity_override=None,
):
    """Executes event loop over ALLEGRO subdetectors and accumulates validation metrics."""
    det_params = det_cfg.get("detector_parameters") or det_cfg.get("geometry", {})
    subdetectors_cfg = det_cfg.get("subdetectors", {})
    dch_cfg = subdetectors_cfg.get("drift_chamber", {})
    collections_cfg = det_cfg.get("collections", {})

    # Global detector parameters
    magnetic_field_tesla = det_params.get("magnetic_field_tesla", 2.0)
    sigma_multiplier = det_params.get("sigma_multiplier", 3.0)
    max_eta = (
        max_pseudorapidity_override
        if max_pseudorapidity_override is not None
        else det_params.get("max_pseudorapidity", 0.88)
    )

    # Drift Chamber specific parameters (with fallback for backward compatibility)
    total_drift_chamber_layers = dch_cfg.get(
        "total_layers", det_params.get("total_drift_chamber_layers", 112)
    )
    superlayer_bit_name = dch_cfg.get(
        "superlayer_bit_name", det_params.get("superlayer_bit_name", "superlayer")
    )
    layer_bit_name = dch_cfg.get(
        "layer_bit_name", det_params.get("layer_bit_name", "layer")
    )

    if bitfield_decoder is None:
        bitfield_decoder = init_bitfield_coder(det_cfg, logger)

    track_collections = collections_cfg.get(
        "track_collections", ["FittedTracks", "FittedTracksWithFilteredHits"]
    )

    histo_defs = resolve_histogram_definitions(det_cfg, logger)
    data_registry = {key: [] for key in histo_defs.keys()}
    accepted_count_total, accepted_count_eta = 0, 0

    events = podio_reader.get("events")
    logger.info(f"[{particle_prefix}] Processing events...")

    for event_index, event_data in enumerate(events):
        accepted_count_total += 1

        # Primary MC Particle
        mc_col_name = collections_cfg.get("mc_particles", "MCParticles")
        mc_particles = event_data.get(mc_col_name) or []
        primary_mc_particle = next(
            (p for p in mc_particles if p.getGeneratorStatus() == 1), None
        )
        if not primary_mc_particle:
            continue

        true_mc_energy = primary_mc_particle.getEnergy()

        # Eta Acceptance & Silicon/Drift Chamber Occupancies
        is_accepted_eta, _ = evaluate_particle_eta_acceptance(event_data, max_eta)
        if is_accepted_eta:
            accepted_count_eta += 1
            layer_hits = Counter()

            dch_col_name = collections_cfg.get("dch_digis", "DCHDigis")
            drift_chamber_digi_hits = event_data.get(dch_col_name) or []

            for hit in drift_chamber_digi_hits:
                cell_id = hit.getCellID()
                superlayer_val = bitfield_decoder.get(cell_id, superlayer_bit_name)
                layer_val = bitfield_decoder.get(cell_id, layer_bit_name)
                global_layer_index = superlayer_val * 8 + layer_val
                layer_hits[global_layer_index] += 1

            if "drift_chamber_hits_per_layer" in data_registry:
                data_registry["drift_chamber_hits_per_layer"].extend(
                    [0] * (total_drift_chamber_layers - len(layer_hits))
                )
                data_registry["drift_chamber_hits_per_layer"].extend(
                    layer_hits.values()
                )

            vtx_cols = collections_cfg.get("vtx_digis", ["VTXBDigis", "VTXDDigis"])
            vtx_hits = sum(len(event_data.get(col) or []) for col in vtx_cols)
            if "vtx_digi_hits_per_event" in data_registry:
                data_registry["vtx_digi_hits_per_event"].append(vtx_hits)

            siwr_cols = collections_cfg.get(
                "si_wrapper_digis", ["SiWrBDigis", "SiWrDDigis"]
            )
            siwr_hits = sum(len(event_data.get(col) or []) for col in siwr_cols)
            if "siwr_digi_hits_per_event" in data_registry:
                data_registry["siwr_digi_hits_per_event"].append(siwr_hits)

        # Drift Chamber dN/dx Collection PID
        if "dch_dndx_value" in data_registry or "dch_dn_dx" in data_registry:
            dndx_key = (
                "dch_dndx_value" if "dch_dndx_value" in data_registry else "dch_dn_dx"
            )
            dndx_col_name = collections_cfg.get(
                "dch_dndx",
                collections_cfg.get("drift_chamber_dndx", "DCHdNdxCollection"),
            )
            for dqdx_obj in event_data.get(dndx_col_name) or []:
                dqdx_val = getattr(dqdx_obj.getDQdx(), "value", dqdx_obj.getDQdx())
                data_registry[dndx_key].append(dqdx_val)

        # Track-to-MC Truth Mapping
        assoc_col_name = collections_cfg.get(
            "track_mc_assoc",
            collections_cfg.get(
                "track_mc_association", "TracksFromGenParticlesAssociation"
            ),
        )
        global_track_to_mc_map = extract_track_to_mc_map(event_data.get(assoc_col_name))

        # Topological Clusters & Calorimetry
        topocluster_cols = collections_cfg.get(
            "topoclusters", ["AugmentedCaloTopoClusters", "AugmentedCaloClusters"]
        )
        topocluster_list = []
        for col in topocluster_cols:
            c_list = event_data.get(col)
            if c_list:
                topocluster_list = list(c_list)
                break

        if "topocluster_count" in data_registry:
            data_registry["topocluster_count"].append(len(topocluster_list))

        if (
            topocluster_list
            and true_mc_energy > 0
            and "topocluster_truth_response" in data_registry
        ):
            leading_cluster_E = max(c.getEnergy() for c in topocluster_list)
            data_registry["topocluster_truth_response"].append(
                leading_cluster_E / true_mc_energy
            )

        # LAr ECal & HCal Calorimeter Hits
        ecal_barrel_col = collections_cfg.get(
            "ecal_barrel_hits", "ECalBarrelModuleThetaMergedPositioned"
        )
        ecal_endcap_col = collections_cfg.get(
            "ecal_endcap_hits", "ECalEndcapTurbinePositioned"
        )
        hcal_endcap_col = collections_cfg.get(
            "hcal_endcap_hits", "HCalEndcapReadoutPositioned"
        )

        ecal_barrel_hits = event_data.get(ecal_barrel_col) or []
        ecal_endcap_hits = event_data.get(ecal_endcap_col) or []
        hcal_endcap_hits = event_data.get(hcal_endcap_col) or []

        if "ecal_cell_hits_per_event" in data_registry:
            data_registry["ecal_cell_hits_per_event"].append(
                len(ecal_barrel_hits) + len(ecal_endcap_hits)
            )

        ecal_barrel_E = sum(h.getEnergy() for h in ecal_barrel_hits)
        ecal_endcap_E = sum(h.getEnergy() for h in ecal_endcap_hits)
        hcal_endcap_E = sum(h.getEnergy() for h in hcal_endcap_hits)

        total_ecal_E = ecal_barrel_E + ecal_endcap_E
        total_calo_reco_E = total_ecal_E + hcal_endcap_E

        if true_mc_energy > 0 and "total_calo_energy_linearity" in data_registry:
            data_registry["total_calo_energy_linearity"].append(
                total_calo_reco_E / true_mc_energy
            )

        if total_calo_reco_E > 0 and "ecal_shower_fraction" in data_registry:
            data_registry["ecal_shower_fraction"].append(
                total_ecal_E / total_calo_reco_E
            )

        # Tracking Performance
        for col_name in track_collections:
            reconstructed_tracks = event_data.get(col_name) or []
            valid_track_count = 0

            for track in reconstructed_tracks:
                if track.trackerHits_size() == 0:
                    continue

                valid_track_count += 1
                if (
                    is_accepted_eta
                    and f"tracker_hits_per_track_{col_name}" in data_registry
                ):
                    data_registry[f"tracker_hits_per_track_{col_name}"].append(
                        track.trackerHits_size()
                    )

                if (
                    track.getNdf() > 0
                    and f"track_fit_chi2_over_ndf_{col_name}" in data_registry
                ):
                    data_registry[f"track_fit_chi2_over_ndf_{col_name}"].append(
                        track.getChi2() / track.getNdf()
                    )

                if track.trackStates_size() > 0:
                    track_state = track.getTrackStates()[0]

                    if f"track_impact_parameter_d0_{col_name}" in data_registry:
                        data_registry[f"track_impact_parameter_d0_{col_name}"].append(
                            track_state.D0
                        )

                    p_reco = calculate_track_momentum(track_state, magnetic_field_tesla)
                    if (
                        p_reco > 0
                        and f"momentum_resolution_{col_name}" in data_registry
                    ):
                        matched_mc = global_track_to_mc_map.get(
                            track.getObjectID(), primary_mc_particle
                        )
                        if matched_mc:
                            p_mc = matched_mc.getMomentum()
                            true_p = math.sqrt(p_mc.x**2 + p_mc.y**2 + p_mc.z**2)
                            if true_p > 0:
                                data_registry[f"momentum_resolution_{col_name}"].append(
                                    (p_reco - true_p) / true_p
                                )

                    # Track-Cluster Matching (E/p)
                    if (
                        col_name == track_collections[0]
                        and "track_ep_ratio" in data_registry
                        and p_reco > 0
                    ):
                        track_dir_mag = math.sqrt(1.0 + track_state.tanLambda**2)
                        tx = math.cos(track_state.phi) / track_dir_mag
                        ty = math.sin(track_state.phi) / track_dir_mag
                        tz = track_state.tanLambda / track_dir_mag

                        min_delta_r, matched_E = float("inf"), 0.0
                        for cluster in topocluster_list:
                            pos = cluster.getPosition()
                            pos_mag = math.sqrt(pos.x**2 + pos.y**2 + pos.z**2)
                            if pos_mag > 0:
                                cx, cy, cz = (
                                    pos.x / pos_mag,
                                    pos.y / pos_mag,
                                    pos.z / pos_mag,
                                )
                                dot_product = max(
                                    -1.0, min(1.0, tx * cx + ty * cy + tz * cz)
                                )
                                delta_r = math.acos(dot_product)
                                if delta_r < min_delta_r:
                                    min_delta_r = delta_r
                                    matched_E = cluster.getEnergy()

                        if min_delta_r < 0.2:
                            data_registry["track_ep_ratio"].append(matched_E / p_reco)

            if f"reconstructed_tracks_per_event_{col_name}" in data_registry:
                data_registry[f"reconstructed_tracks_per_event_{col_name}"].append(
                    valid_track_count
                )

    logger.info(
        f"[{particle_prefix}] Event processing complete. Generating histograms..."
    )
    return build_and_fill_histograms(
        data_registry=data_registry,
        histo_defs=histo_defs,
        particle_prefix=particle_prefix,
        accepted_count_total=accepted_count_total,
        accepted_count_eta=accepted_count_eta,
        sigma_multiplier=sigma_multiplier,
        logger=logger,
        config=det_cfg,
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="ALLEGRO detector simulation histogram extraction engine."
    )
    parser.add_argument("--input", required=True, help="Input PODIO ROOT file path")
    parser.add_argument(
        "--output", required=True, help="Output ROOT histogram file path"
    )
    parser.add_argument(
        "--particle-prefix",
        required=True,
        help="Particle prefix label (e.g. electron, muon)",
    )
    parser.add_argument(
        "--config",
        "--detector-config",
        dest="config",
        default="config/ALLEGRO/ALLEGRO_o1_v03/config.yaml",
        help="Detector configuration YAML file path",
    )
    parser.add_argument(
        "--max-pseudorapidity",
        type=float,
        default=None,
        help="Optional max pseudorapidity cutoff override",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    ROOT.gROOT.SetBatch(True)

    logger.info("Starting ALLEGRO histogram generation execution.")
    logger.info(f"Input file:       {args.input}")
    logger.info(f"Output file:      {args.output}")
    logger.info(f"Particle prefix:  {args.particle_prefix}")
    logger.info(f"Detector config:  {args.config}")

    try:
        with open(args.config, "r") as f:
            det_cfg = yaml.safe_load(f)
        logger.debug("Loaded detector configuration YAML successfully.")
    except Exception as e:
        logger.error(f"Failed to load detector configuration '{args.config}': {e}")
        sys.exit(1)

    reader = open_podio_root_reader(args.input)
    if not reader:
        logger.error(f"Could not initialize PODIO reader for: {args.input}")
        sys.exit(1)

    histogram_registry = analyze_detector_simulation_file(
        podio_reader=reader,
        particle_prefix=args.particle_prefix,
        det_cfg=det_cfg,
        max_pseudorapidity_override=args.max_pseudorapidity,
    )

    write_histograms_to_file(histogram_registry, args.output)
    logger.info("ALLEGRO histogram extraction completed successfully.")


if __name__ == "__main__":
    main()
