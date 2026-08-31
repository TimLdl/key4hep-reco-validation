"""Shared helper utilities for histogram building, ROOT styling, and configuration parsing.

This module is imported by both the histogram extraction pipeline (``engine.py``)
and the plotting engine (``plotting.py``). All functions are detector-agnostic.

Key function groups:

- **Histogram building**: :func:`resolve_histogram_definitions`, :func:`build_and_fill_histograms`
- **Config discovery**: :func:`discover_validation_configs`
- **ROOT helpers**: :func:`apply_root_graphics_style`, :func:`optimize_axis_ticks`, :func:`draw_title_latex`
- **KS test**: :func:`compute_ks_test`
- **Physics utilities**: :func:`evaluate_particle_eta_acceptance`, :func:`calculate_track_momentum`
- **Event data access**: :func:`extract_track_to_mc_map`, :func:`get_collection_hits`
- **Detector geometry**: :func:`init_bitfield_coder`
"""

import math
import os
import sys
from pathlib import Path
from dd4hep import dd4hep
import numpy as np
import ROOT
import yaml

from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("helpers")


def get_event_count(hist):
    """Extracts actual accepted event count from histogram metadata instead of bin entries."""
    if hasattr(hist, "accepted_events"):
        return getattr(hist, "accepted_events")
    if hasattr(hist, "GetListOfFunctions") and hist.GetListOfFunctions():
        obj = hist.GetListOfFunctions().FindObject("accepted_events")
        if obj:
            try:
                return int(obj.GetTitle())
            except (ValueError, TypeError):
                pass
    return int(hist.GetEntries())


def discover_validation_configs(target_path):
    """Discovers YAML validation configs from a file or directory path."""
    p = Path(target_path)
    if p.is_file():
        return [str(p)]
    if p.is_dir():
        configs = []
        for entry in sorted(p.glob("*.yaml")):
            if entry.name not in ["plotting.yaml", "web.yaml"]:
                configs.append(str(entry))
        return configs
    return []


def find_histogram(registry, dataset_key, plot_key):
    """Flexible registry search supporting raw keys and prefixed names."""
    candidate_keys = [
        plot_key,
        f"h_{dataset_key}_{plot_key}",
        f"h_{plot_key}",
    ]
    for cand in candidate_keys:
        if cand in registry:
            return registry[cand]

    for reg_key, hist in registry.items():
        if reg_key.endswith(plot_key):
            return hist
    return None


def apply_root_graphics_style(cfg):
    """Configures global ROOT graphics style parameters."""
    ROOT.gROOT.ForceStyle(True)
    ROOT.gStyle.SetCanvasColor(cfg.get("canvas_color", ROOT.kWhite))
    ROOT.gStyle.SetPadColor(cfg.get("pad_color", ROOT.kWhite))
    ROOT.gStyle.SetOptStat(cfg.get("opt_stat", 0))
    ROOT.gStyle.SetOptTitle(cfg.get("opt_title", 0))
    ROOT.gStyle.SetPadTopMargin(cfg.get("margin_top", 0.10))
    ROOT.gStyle.SetPadBottomMargin(cfg.get("margin_bottom", 0.14))
    ROOT.gStyle.SetPadLeftMargin(cfg.get("margin_left", 0.16))
    ROOT.gStyle.SetPadRightMargin(cfg.get("margin_right", 0.06))

    font_type = cfg.get("font_type", 42)
    ROOT.gStyle.SetLabelFont(font_type, "XYZ")
    ROOT.gStyle.SetLabelSize(cfg.get("label_size", 0.045), "XYZ")
    ROOT.gStyle.SetTitleFont(font_type, "XYZ")
    ROOT.gStyle.SetTitleSize(cfg.get("title_size", 0.055), "XYZ")
    ROOT.gStyle.SetTitleOffset(1.1, "X")
    ROOT.gStyle.SetTitleOffset(1.3, "Y")


def optimize_axis_ticks(hist):
    """Formats numeric axis divisions and integer labels cleanly."""
    x_axis = hist.GetXaxis()
    y_axis = hist.GetYaxis()
    x_axis.SetNdivisions(510, ROOT.kTRUE)
    y_axis.SetNdivisions(510, ROOT.kTRUE)

    if hist.InheritsFrom("TH1I") or isinstance(hist, ROOT.TH1I):
        x_axis.SetDecimals(ROOT.kFALSE)


def draw_title_latex(title_text, canvas):
    """Draws pad title via TLatex dynamically scaled for text length."""
    if not title_text:
        return None

    latex = ROOT.TLatex()
    latex.SetNDC()
    latex.SetTextFont(42)

    base_size = 0.038
    max_len = 50
    if len(title_text) > max_len:
        base_size = base_size * (max_len / len(title_text))

    latex.SetTextSize(max(0.022, base_size))
    x_pos = ROOT.gStyle.GetPadLeftMargin()
    y_pos = 1.0 - ROOT.gStyle.GetPadTopMargin() + 0.02

    latex.DrawLatex(x_pos, y_pos, title_text)
    return latex


def compute_ks_test(data_hist, ref_hist, confidence_level=0.05, option=""):
    """
    Calculates two-sample Kolmogorov-Smirnov test p-value and pass/fail status.
    For 2D histograms, performs the KS test on 1D X and Y projections.

    Args:
        data_hist: ROOT TH1 or TH2 instance for target data.
        ref_hist: ROOT TH1 or TH2 instance for reference data.
        confidence_level: Significance threshold (alpha) for hypothesis testing.
        option: ROOT KolmogorovTest string option (e.g., 'M', 'D').

    Returns:
        dict: Test metrics containing p-value(s), pass/fail boolean, and confidence level.
        None: Returned if histograms are missing or type mismatch occurs.
    """
    if not data_hist or not ref_hist:
        return None

    try:
        is_2d_data = data_hist.InheritsFrom("TH2") or isinstance(data_hist, ROOT.TH2)
        is_2d_ref = ref_hist.InheritsFrom("TH2") or isinstance(ref_hist, ROOT.TH2)

        if is_2d_data or is_2d_ref:
            if not (is_2d_data and is_2d_ref):
                logger.warning(
                    "KS test mismatch: one histogram is 2D and the other is 1D."
                )
                return None

            # Project 2D histogram onto X axis
            px_data = data_hist.ProjectionX(f"{data_hist.GetName()}_px_data")
            px_ref = ref_hist.ProjectionX(f"{ref_hist.GetName()}_px_ref")
            px_data.SetDirectory(0)
            px_ref.SetDirectory(0)
            p_val_x = float(px_data.KolmogorovTest(px_ref, option))

            # Project 2D histogram onto Y axis
            py_data = data_hist.ProjectionY(f"{data_hist.GetName()}_py_data")
            py_ref = ref_hist.ProjectionY(f"{ref_hist.GetName()}_py_ref")
            py_data.SetDirectory(0)
            py_ref.SetDirectory(0)
            p_val_y = float(py_data.KolmogorovTest(py_ref, option))

            passed = (p_val_x >= confidence_level) and (p_val_y >= confidence_level)

            return {
                "p_value": {"x": p_val_x, "y": p_val_y},
                "passed": passed,
                "confidence_level": confidence_level,
                "is_2d": True,
            }
        else:
            p_val = float(data_hist.KolmogorovTest(ref_hist, option))
            passed = p_val >= confidence_level
            return {
                "p_value": p_val,
                "passed": passed,
                "confidence_level": confidence_level,
                "is_2d": False,
            }
    except Exception as e:
        logger.warning(f"Failed to calculate Kolmogorov-Smirnov test: {e}")
        return None


def evaluate_particle_eta_acceptance(primary_mc, max_eta=None):
    """Evaluates whether primary MC particle falls within pseudorapidity acceptance."""
    if max_eta is None or not primary_mc:
        return True, 0.0

    p = primary_mc.getMomentum()
    p_mag = math.sqrt(p.x**2 + p.y**2 + p.z**2)
    if p_mag == 0 or abs(p.z) >= p_mag:
        return False, 0.0

    theta = math.acos(p.z / p_mag)
    eta = -math.log(math.tan(theta / 2.0))
    return abs(eta) <= max_eta, eta


def init_bitfield_coder(config, logger=None):
    """Initializes DD4hep BitFieldCoder from configuration parameters."""
    geom_cfg = config.get("geometry", {})
    detector_parameters = config.get("detector_parameters", {})

    bitfield_str = geom_cfg.get("bitfield") or detector_parameters.get(
        "bitfield_string"
    )
    if not bitfield_str:
        for subdetector_config in config.get("subdetectors", {}).values():
            if (
                isinstance(subdetector_config, dict)
                and "bitfield_string" in subdetector_config
            ):
                bitfield_str = subdetector_config["bitfield_string"]
                break

    if not bitfield_str:
        if logger:
            logger.debug("No bitfield pattern defined in configuration.")
        return None

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
    """Expands YAML plot definitions based on collection parameters."""
    histo_defs = {}
    collections_config = config.get("collections", {})
    track_collections = collections_config.get("track_collections", [])

    for plot in config.get("plots", []):
        key = plot["key"]
        title = plot["title"]
        plot_type = plot.get("type", "asymmetric")
        x_title = plot.get("x_title", "")
        apply_eta_cut = plot.get("apply_eta_cut", plot.get("eta_gated", False))
        bins = plot.get("bins", 100)
        xmin = plot.get("xmin", 0.0)
        xmax = plot.get("xmax", 1.0)

        if plot.get("per_collection"):
            for col in track_collections:
                full_key = f"{key}_{col}"
                histo_defs[full_key] = {
                    "key": full_key,
                    "title": f"{title} ({col});{x_title};Entries",
                    "type": plot_type,
                    "x_title": x_title,
                    "apply_eta_cut": apply_eta_cut,
                    "bins": bins,
                    "xmin": xmin,
                    "xmax": xmax,
                }
        else:
            histo_defs[key] = {
                "key": key,
                "title": f"{title};{x_title};Entries",
                "type": plot_type,
                "x_title": x_title,
                "apply_eta_cut": apply_eta_cut,
                "bins": bins,
                "xmin": xmin,
                "xmax": xmax,
            }

    if logger:
        logger.info(f"Resolved {len(histo_defs)} histogram definition(s).")
    return histo_defs


def extract_track_to_mc_map(assoc_collection, logger=None):
    """Parses track-to-MC truth association links into an object-ID map."""
    track_to_mc_map = {}
    if not assoc_collection:
        return track_to_mc_map

    for association in assoc_collection:
        if hasattr(association, "getRec"):
            source_object, target_object = association.getRec(), association.getSim()
        elif hasattr(association, "getLeft"):
            source_object, target_object = (
                association.getLeft(),
                association.getRight(),
            )
        elif hasattr(association, "getFrom"):
            source_object, target_object = (
                association.getFrom(),
                association.getTo(),
            )
        else:
            if logger:
                logger.warning(
                    "Skipping association without a supported link interface"
                )
            continue

        if not source_object or not target_object:
            continue
        track_object, mc_object = (
            (source_object, target_object)
            if hasattr(source_object, "getTrackStates")
            else (target_object, source_object)
        )
        if track_object and mc_object:
            track_to_mc_map[track_object.getObjectID()] = mc_object
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
    """Constructs ROOT histograms and attaches true accepted event metadata."""
    histogram_registry = {}

    for key, meta in histo_defs.items():
        if key not in data_registry:
            continue

        raw_pts = np.array(data_registry[key], dtype=float)
        pts = raw_pts[np.isfinite(raw_pts)]

        bins = meta.get("bins", 100)
        xmin = meta.get("xmin", 0.0)
        xmax = meta.get("xmax", 1.0)

        hist_name = f"h_{particle_prefix}_{key}"
        histogram = (
            ROOT.TH1I(hist_name, meta["title"], bins, xmin, xmax)
            if meta.get("type") == "integer"
            else ROOT.TH1D(hist_name, meta["title"], bins, xmin, xmax)
        )
        histogram.SetDirectory(0)
        histogram.GetXaxis().SetTitle(meta.get("x_title", ""))
        histogram.GetYaxis().SetTitle("Entries")

        if meta.get("type") == "integer":
            if bins <= 20:
                histogram.GetXaxis().SetNdivisions(bins, False)
            else:
                histogram.GetXaxis().SetNdivisions(510)

        bin_width = (xmax - xmin) / bins
        first_bin_center = xmin + 0.5 * bin_width
        last_bin_center = xmax - 0.5 * bin_width

        clamped_pts = np.clip(pts, first_bin_center, last_bin_center)
        for val in clamped_pts:
            histogram.Fill(val)

        apply_eta_cut = meta.get("apply_eta_cut", meta.get("eta_gated", False))
        accepted_cnt = accepted_count_eta if apply_eta_cut else accepted_count_total

        # Attach true event count directly to metadata
        histogram.accepted_events = accepted_cnt
        existing_info = histogram.GetListOfFunctions().FindObject("accepted_events")
        if existing_info:
            histogram.GetListOfFunctions().Remove(existing_info)
        histogram.GetListOfFunctions().Add(
            ROOT.TNamed("accepted_events", str(accepted_cnt))
        )

        histogram_registry[key] = histogram

    return histogram_registry


def get_collection_hits(ctx, key):
    """Retrieves objects from single or multiple collection names."""
    collections_config = ctx.config.get("collections", {})
    collection_names = collections_config.get(key, [])
    if isinstance(collection_names, str):
        collection_names = [collection_names]
    hits = []
    for collection_name in collection_names:
        hits.extend(ctx.event_data.get(collection_name) or [])
    return hits
