import math
import os
import shutil
import sys
from collections import Counter
from dd4hep import dd4hep
import numpy as np
import ROOT

from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("helpers")


def evaluate_particle_eta_acceptance(event_data, max_eta=None):
    """Evaluates whether the primary MC particle falls within the detector pseudorapidity acceptance."""
    if max_eta is None:
        return True, 0.0

    mc_particles = event_data.get("MCParticles") or []
    primary_mc = next((p for p in mc_particles if p.getGeneratorStatus() == 1), None)

    if not primary_mc:
        return False, 0.0

    p = primary_mc.getMomentum()
    p_mag = math.sqrt(p.x**2 + p.y**2 + p.z**2)
    if p_mag == 0 or abs(p.z) >= p_mag:
        return False, 0.0

    theta = math.acos(p.z / p_mag)
    eta = -math.log(math.tan(theta / 2.0))
    return abs(eta) <= max_eta, eta


def init_bitfield_coder(config, logger=None):
    """Initializes and returns a DD4hep BitFieldCoder from configuration parameters."""
    geom_cfg = config.get("geometry", {})
    det_params = config.get("detector_parameters", {})

    bitfield_str = geom_cfg.get("bitfield") or det_params.get(
        "bitfield_string",
        "system:5,side:-2,module:8,sensor:8,superlayer:6,layer:8",
    )

    try:
        coder = dd4hep.BitFieldCoder(bitfield_str)
        if logger:
            logger.debug(
                f"DD4hep BitFieldCoder initialized with pattern: '{bitfield_str}'"
            )
        return coder
    except Exception as e:
        if logger:
            logger.error(f"Failed to initialize DD4hep BitFieldCoder: {e}")
        sys.exit(1)


def resolve_histogram_definitions(config, logger=None):
    """Expands YAML plot definitions based on collection parameters and collections mapping."""
    histo_defs = {}
    collections_cfg = config.get("collections", {})
    track_collections = collections_cfg.get("track_collections", [])

    for plot in config.get("plots", []):
        key = plot["key"]
        title = plot["title"]
        plot_type = plot.get("type", "asymmetric")
        x_title = plot.get("x_title", "")
        eta_gated = plot.get("eta_gated", False)

        if plot.get("per_collection"):
            for col in track_collections:
                full_key = f"{key}_{col}"
                histo_defs[full_key] = {
                    "key": full_key,
                    "title": f"{title} ({col});{x_title};Entries",
                    "type": plot_type,
                    "x_title": x_title,
                    "eta_gated": eta_gated,
                }
        else:
            histo_defs[key] = {
                "key": key,
                "title": f"{title};{x_title};Entries",
                "type": plot_type,
                "x_title": x_title,
                "eta_gated": eta_gated,
            }

    if logger:
        logger.info(f"Resolved {len(histo_defs)} histogram definition(s).")
    return histo_defs


def extract_track_to_mc_map(assoc_collection):
    """Parses track-to-MC truth association links into an object-ID map."""
    track_to_mc_map = {}
    if not assoc_collection:
        return track_to_mc_map

    for link in assoc_collection:
        try:
            src, tgt = (
                (link.getRec(), link.getSim())
                if hasattr(link, "getRec")
                else (link.getLeft(), link.getRight())
            )
            if src and tgt:
                track_obj, mc_obj = (
                    (src, tgt) if hasattr(src, "getTrackStates") else (tgt, src)
                )
                if track_obj and mc_obj:
                    track_to_mc_map[track_obj.getObjectID()] = mc_obj
        except Exception:
            pass
    return track_to_mc_map


def calculate_track_momentum(track_state, magnetic_field_tesla):
    """Calculates total reconstructed momentum (p) from track state helix parameters."""
    if abs(track_state.omega) <= 1e-7:
        return 0.0
    p_transverse = (0.299792458 * magnetic_field_tesla) / (
        1000.0 * abs(track_state.omega)
    )
    return p_transverse * math.sqrt(1.0 + track_state.tanLambda**2)


def build_and_fill_histograms(
    data_registry,
    histo_defs,
    particle_prefix,
    accepted_count_total,
    accepted_count_eta,
    sigma_multiplier=3.0,
    logger=None,
    config=None,
):
    """Constructs ROOT histograms, cleans non-finite data, populates bins, and sets event normalization metadata."""
    if config and "detector_parameters" in config:
        sigma_multiplier = config["detector_parameters"].get(
            "sigma_multiplier", sigma_multiplier
        )

    histogram_registry = {}

    for key, meta in histo_defs.items():
        if key not in data_registry:
            continue

        raw_pts = np.array(data_registry[key], dtype=float)
        pts = raw_pts[np.isfinite(raw_pts)]
        n_entries = len(pts)

        if len(raw_pts) > n_entries and logger:
            logger.warning(
                f"[{key}] Discarded {len(raw_pts) - n_entries} non-finite (NaN/Inf) values."
            )

        if n_entries == 0:
            bins, xmin, xmax = 10, 0.0, 1.0
        elif meta["type"] == "integer":
            max_val = np.max(pts)
            high_bound = int(max(1, np.ceil(max_val * 1.5)))
            bins, xmin, xmax = high_bound + 1, -0.5, high_bound + 0.5
        elif meta["type"] == "symmetric":
            bins = int(max(1, np.ceil(2 * (n_entries ** (1 / 3)))))
            sigma = np.std(pts) if np.std(pts) > 0 else 1.0
            mean = np.mean(pts)
            xmin, xmax = (
                mean - sigma_multiplier * sigma,
                mean + sigma_multiplier * sigma,
            )
        elif meta["type"] == "asymmetric":
            bins = int(max(1, np.ceil(2 * (n_entries ** (1 / 3)))))
            max_val = np.max(pts)
            xmin, xmax = 0.0, (max_val * 1.5 if max_val > 0 else 1.0)

        if xmin >= xmax or np.isnan(xmin) or np.isnan(xmax):
            xmin, xmax = 0.0, 1.0

        hist_name = f"h_{particle_prefix}_{key}"
        histogram = (
            ROOT.TH1I(hist_name, meta["title"], bins, xmin, xmax)
            if meta["type"] == "integer"
            else ROOT.TH1D(hist_name, meta["title"], bins, xmin, xmax)
        )
        histogram.SetDirectory(0)
        histogram.GetXaxis().SetTitle(meta.get("x_title", ""))
        histogram.GetYaxis().SetTitle("Entries")

        bin_width = (xmax - xmin) / bins if bins > 0 else 1.0
        for val in pts:
            if val < xmin:
                histogram.Fill(xmin + 0.5 * bin_width)
            elif val >= xmax:
                histogram.Fill(xmax - 0.5 * bin_width)
            else:
                histogram.Fill(val)

        is_eta_gated = meta.get("eta_gated", False)
        accepted_cnt = accepted_count_eta if is_eta_gated else accepted_count_total
        histogram.accepted_events = accepted_cnt

        # Store metadata in GetListOfFunctions() to ensure persistence in ROOT files
        existing_info = histogram.GetListOfFunctions().FindObject("accepted_events")
        if existing_info:
            histogram.GetListOfFunctions().Remove(existing_info)
        histogram.GetListOfFunctions().Add(
            ROOT.TNamed("accepted_events", str(accepted_cnt))
        )

        histogram_registry[key] = histogram

    return histogram_registry


def clear_directory(directory_path):
    if os.path.exists(directory_path):
        try:
            shutil.rmtree(directory_path)
            logger.info(f"Cleared existing directory: {directory_path}")
        except Exception as e:
            logger.error(f"Failed to clear directory '{directory_path}': {e}")
            raise
    else:
        logger.debug(f"Directory does not exist yet, creating: {directory_path}")

    try:
        os.makedirs(directory_path, exist_ok=True)
        logger.debug(f"Successfully ensured directory path exists: {directory_path}")
    except Exception as e:
        logger.error(f"Failed to create directory '{directory_path}': {e}")
        raise
