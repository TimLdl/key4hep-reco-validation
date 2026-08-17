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

logger = setup_logger("IDEA_hist")


def analyze_detector_simulation_file(
    podio_reader,
    particle_prefix: str,
    det_cfg: dict,
    bitfield_decoder=None,
    max_pseudorapidity_override=None,
):
    """Executes event loop over IDEA subdetectors and accumulates validation metrics."""
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

            vtx_b = event_data.get(collections_cfg.get("vtx_barrel_digis")) or []
            vtx_d = event_data.get(collections_cfg.get("vtx_endcap_digis")) or []
            if "vtx_digi_hits_per_event" in data_registry:
                data_registry["vtx_digi_hits_per_event"].append(len(vtx_b) + len(vtx_d))

            siwr_b = event_data.get(collections_cfg.get("siwr_barrel_digis")) or []
            siwr_d = event_data.get(collections_cfg.get("siwr_endcap_digis")) or []
            if "siwr_digi_hits_per_event" in data_registry:
                data_registry["siwr_digi_hits_per_event"].append(
                    len(siwr_b) + len(siwr_d)
                )

            if "drift_chamber_hits_per_layer" in data_registry:
                layer_hits = Counter()
                dch_digis = (
                    event_data.get(collections_cfg.get("drift_chamber_digis")) or []
                )
                for hit in dch_digis:
                    cell_id = hit.getCellID()
                    idx = bitfield_decoder.get(
                        cell_id, superlayer_bit_name
                    ) * 8 + bitfield_decoder.get(cell_id, layer_bit_name)
                    layer_hits[idx] += 1

                data_registry["drift_chamber_hits_per_layer"].extend(
                    [0] * (total_drift_chamber_layers - len(layer_hits))
                )
                data_registry["drift_chamber_hits_per_layer"].extend(
                    layer_hits.values()
                )

            if "muon_system_hits_per_event" in data_registry:
                muon_hits = (
                    event_data.get(collections_cfg.get("muon_tracker_hits")) or []
                )
                data_registry["muon_system_hits_per_event"].append(len(muon_hits))

        # Drift Chamber dN/dx Collection PID
        if "dch_dn_dx" in data_registry or "dch_dndx_value" in data_registry:
            dndx_key = "dch_dn_dx" if "dch_dn_dx" in data_registry else "dch_dndx_value"
            dndx_hits = event_data.get(collections_cfg.get("drift_chamber_dndx")) or []
            for dqdx in dndx_hits:
                val = dqdx.getDQdx().value if hasattr(dqdx, "getDQdx") else None
                if val is not None:
                    data_registry[dndx_key].append(val)

        # Track-to-MC Truth Mapping
        assoc_col_name = collections_cfg.get(
            "track_mc_association",
            collections_cfg.get("track_mc_assoc", "TracksFromGenParticlesAssociation"),
        )
        global_track_to_mc_map = extract_track_to_mc_map(event_data.get(assoc_col_name))

        # Tracking Performance
        for col_name in track_collections:
            tracks = event_data.get(col_name) or []
            valid_tracks = 0
            for t in tracks:
                if t.trackerHits_size() == 0:
                    continue
                valid_tracks += 1
                if (
                    is_accepted_eta
                    and f"tracker_hits_per_track_{col_name}" in data_registry
                ):
                    data_registry[f"tracker_hits_per_track_{col_name}"].append(
                        t.trackerHits_size()
                    )
                if (
                    t.getNdf() > 0
                    and f"track_fit_chi2_over_ndf_{col_name}" in data_registry
                ):
                    data_registry[f"track_fit_chi2_over_ndf_{col_name}"].append(
                        t.getChi2() / t.getNdf()
                    )
                if (
                    t.trackStates_size() > 0
                    and f"momentum_resolution_{col_name}" in data_registry
                ):
                    st = t.getTrackStates()[0]
                    p_reco = calculate_track_momentum(st, magnetic_field_tesla)
                    if p_reco > 0:
                        matched_mc = global_track_to_mc_map.get(
                            t.getObjectID(), primary_mc_particle
                        )
                        if matched_mc:
                            mc_p = matched_mc.getMomentum()
                            p_true = math.sqrt(mc_p.x**2 + mc_p.y**2 + mc_p.z**2)
                            if p_true > 0:
                                data_registry[f"momentum_resolution_{col_name}"].append(
                                    (p_reco - p_true) / p_true
                                )

            if f"reconstructed_tracks_per_event_{col_name}" in data_registry:
                data_registry[f"reconstructed_tracks_per_event_{col_name}"].append(
                    valid_tracks
                )

        # Dual-Readout Calorimetry Metrics
        c_hits = (
            event_data.get(collections_cfg.get("calo_cherenkov", "DRCherenkovHits"))
            or []
        )
        s_hits = (
            event_data.get(
                collections_cfg.get("calo_scintillation", "DRScintillationHits")
            )
            or []
        )
        e_c, e_s = sum(h.getEnergy() for h in c_hits), sum(
            h.getEnergy() for h in s_hits
        )

        if true_mc_energy > 0:
            if "calorimeter_linearity_cherenkov" in data_registry:
                data_registry["calorimeter_linearity_cherenkov"].append(
                    e_c / true_mc_energy
                )
            if "calorimeter_linearity_scintillation" in data_registry:
                data_registry["calorimeter_linearity_scintillation"].append(
                    e_s / true_mc_energy
                )
            if e_s > 0 and "calorimeter_c_over_s_ratio" in data_registry:
                data_registry["calorimeter_c_over_s_ratio"].append(e_c / e_s)

        topos = (
            event_data.get(collections_cfg.get("topoclusters", "CaloTopoClusters"))
            or []
        )
        if "topocluster_count" in data_registry:
            data_registry["topocluster_count"].append(len(topos))
        if topos and "topocluster_leading_energy" in data_registry:
            data_registry["topocluster_leading_energy"].append(
                max(c.getEnergy() for c in topos)
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
        description="IDEA detector simulation histogram extraction engine."
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
        default="config/IDEA/IDEA_o1_v03/config.yaml",
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

    logger.info("Starting IDEA histogram generation execution.")
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
    logger.info("IDEA histogram extraction completed successfully.")


if __name__ == "__main__":
    main()
