"""Detector-agnostic plot rendering engine.

Produces PNG images from ROOT histogram files, organized into a directory
hierarchy consumed by the web builder:

    <output_dir>/<DETECTOR>/<VARIANT>/<validation_slug>/<system_slug>/<plot_key>.png

Usage (CLI)::

    python3 plotting.py \\
        --inputs electron=ALLEGRO_electron_particleGun_hist.root \\
        --detector-config config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml \\
        --style-config   config/plotting.yaml \\
        --output-dir     plots/ \\
        [--ref-dir       references/ALLEGRO/ALLEGRO_o1_v03/]

When a reference directory is given, each reference histogram is overlaid on the
new one, a Kolmogorov-Smirnov test is run against it, and failing plots are
framed in the configured colour. Multi-dimensional histograms are evaluated
through their 1D per-axis projections. The confidence level is read from
``ks_test.confidence_level`` in the style config.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import ROOT
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from detectors.k4_reco_val_utils.helpers import (
    apply_root_graphics_style,
    compute_ks_test,
    draw_title_latex,
    find_histogram,
    get_event_count,
    optimize_axis_ticks,
)
from detectors.k4_reco_val_utils.io import read_histograms_from_file
from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("plotting")


def normalize_slug(value):
    """Return a filesystem-safe directory slug with a uniform underscore convention."""
    cleaned = str(value).strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in cleaned)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "general"


def parse_root_color(color_val, fallback=ROOT.kBlack):
    """Parses hex strings, integer color codes, or ROOT attribute strings into ROOT color IDs."""
    if color_val is None:
        return fallback
    if isinstance(color_val, int):
        return color_val
    if isinstance(color_val, str):
        if color_val.startswith("#"):
            return ROOT.TColor.GetColor(color_val)
        if hasattr(ROOT, color_val):
            return getattr(ROOT, color_val)
    return fallback


def draw_failure_border(canvas, color, width):
    """Frames the canvas in `color` to flag a plot whose KS test failed.

    The canvas background is filled with the border colour and an inset pad
    holds the actual plot, leaving a visible margin of `width` pixels.
    The returned pad is the drawing area and must stay alive until the save.
    """
    canvas.SetFillColor(color)
    canvas.SetBorderMode(0)

    inset_x = float(width) / max(canvas.GetWw(), 1)
    inset_y = float(width) / max(canvas.GetWh(), 1)
    pad = ROOT.TPad(
        f"{canvas.GetName()}_pad", "", inset_x, inset_y, 1.0 - inset_x, 1.0 - inset_y
    )
    pad.SetFillColor(ROOT.gStyle.GetCanvasColor())
    pad.SetBorderMode(0)
    pad.Draw()
    pad.cd()
    return pad


def generate_plot(
    hist,
    filename,
    out_dir,
    config,
    ref_hist=None,
    draw_opt="HIST",
    title=None,
):
    # Load configuration blocks
    canvas_cfg = config.get("canvas", {})
    style_opts = config.get("style", {})
    sample_styles = config.get("sample_styles", {})
    ks_opts = config.get("ks_test", {})
    legend_cfg = config.get("legend", {})

    apply_root_graphics_style(style_opts)
    full_path = os.path.join(out_dir, filename)
    os.makedirs(out_dir, exist_ok=True)

    # Initialize Canvas from config properties
    c_width = canvas_cfg.get("width", 800)
    c_height = canvas_cfg.get("height", 600)
    canvas = ROOT.TCanvas(
        f"c_{hist.GetName()}_{int(time.time()*1000)%1000}", "", c_width, c_height
    )

    n_dim = hist.GetDimension()
    is_multi_dim = n_dim > 1

    # Evaluated before drawing: a failure means the plot goes inside a border pad.
    ks_res = None
    if ref_hist:
        ks_res = compute_ks_test(
            hist,
            ref_hist,
            confidence_level=ks_opts.get("confidence_level", 0.95),
        )

    pad = canvas
    if ks_res is not None and not ks_res["passed"]:
        pad = draw_failure_border(
            canvas,
            parse_root_color(ks_opts.get("failed_color"), ROOT.kRed),
            ks_opts.get("frame_line_width", 2),
        )

    if n_dim == 2:
        pad.SetRightMargin(canvas_cfg.get("right_margin_2d", 0.15))
        if draw_opt == "HIST":
            draw_opt = "COLZ"
    elif n_dim >= 3:
        # COLZ has no meaning for 3D histograms; a box plot is used instead.
        if draw_opt in ("HIST", "COLZ"):
            draw_opt = canvas_cfg.get("draw_opt_3d", "BOX2Z")
        pad.SetRightMargin(canvas_cfg.get("right_margin_2d", 0.15))

    n_ev_data = get_event_count(hist)
    line_width = style_opts.get("line_width", 1)

    # Apply data styling from config
    data_style = sample_styles.get("data", {})
    data_color = parse_root_color(data_style.get("color"))
    data_line_style = data_style.get("style", 1)
    data_label = data_style.get("label", "Data")

    if not is_multi_dim:
        hist.SetLineColor(data_color)
        hist.SetLineStyle(data_line_style)
        hist.SetLineWidth(line_width)

    legend = None
    if ref_hist:
        ref_style = sample_styles.get("reference", {})
        ref_color = parse_root_color(ref_style.get("color"))
        ref_line_style = ref_style.get("style", 1)
        ref_label = ref_style.get("label", "Reference")

        if not is_multi_dim:
            ref_hist.SetLineColor(ref_color)
            ref_hist.SetLineStyle(ref_line_style)
            ref_hist.SetLineWidth(line_width)

            y_scale = style_opts.get("y_axis_scale", 1.2)
            max_y = max(hist.GetMaximum(), ref_hist.GetMaximum()) * y_scale
            hist.SetMaximum(max_y)

            hist.Draw(draw_opt)
            ref_hist.Draw(f"{draw_opt} SAME")
        else:
            hist.Draw(draw_opt)

        n_ev_ref = get_event_count(ref_hist)

        # Construct legend from config coordinates and font parameters
        legend = ROOT.TLegend(
            legend_cfg.get("x1", 0.5),
            legend_cfg.get("y1", 0.65),
            legend_cfg.get("x2", 0.9),
            legend_cfg.get("y2", 0.88),
        )
        legend.SetBorderSize(legend_cfg.get("border_size", 0))
        legend.SetFillStyle(legend_cfg.get("fill_style", 0))
        legend.SetTextFont(legend_cfg.get("text_font", 42))
        legend.SetTextSize(legend_cfg.get("text_size", 0.03))

        # 2D/3D histograms draw no reference curve, so list it as text only.
        if is_multi_dim:
            legend.AddEntry("", f"{data_label} (N_{{ev}} = {n_ev_data})", "")
            legend.AddEntry("", f"{ref_label} (N_{{ev}} = {n_ev_ref})", "")
        else:
            legend.AddEntry(hist, f"{data_label} (N_{{ev}} = {n_ev_data})", "l")
            legend.AddEntry(ref_hist, f"{ref_label} (N_{{ev}} = {n_ev_ref})", "l")

        if ks_res is not None:
            status_str = "Pass" if ks_res["passed"] else "Fail"
            if ks_res["dimension"] > 1:
                axes = "/".join(ax.upper() for ax in ks_res["p_value"])
                vals = " / ".join(f"{p:.3f}" for p in ks_res["p_value"].values())
                legend.AddEntry("", f"KS p({axes}): {vals} [{status_str}]", "")
            else:
                p_val = ks_res["p_value"]
                legend.AddEntry("", f"KS p-val: {p_val:.4f} [{status_str}]", "")
        legend.Draw()
    else:
        hist.Draw(draw_opt)

    optimize_axis_ticks(hist)
    plot_title = (
        f"{title}  (N_{{ev}} = {n_ev_data})" if title and not ref_hist else title
    )
    latex = draw_title_latex(plot_title, pad)

    canvas.SaveAs(full_path)
    logger.debug(f"Saved plot: {full_path}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help=(
            "Input ROOT histogram file(s) in 'validation_name=path' format. "
            "The validation_name (e.g. 'electron') becomes the particle directory "
            "in the output hierarchy and is used for reference file lookup."
        ),
    )
    parser.add_argument(
        "--detector-config",
        required=True,
        help="Per-particle validation config YAML (defines plots, collections, etc.)",
    )
    parser.add_argument(
        "--style-config",
        default="config/plotting.yaml",
        help="Global ROOT visual style configuration YAML",
    )
    parser.add_argument(
        "--output-dir",
        default="output/plots",
        help="Root output directory; PNGs are written under <output_dir>/<DETECTOR>/<VARIANT>/<validation_slug>/<system_slug>/",
    )
    parser.add_argument(
        "--ref-dir",
        default=None,
        help=(
            "Optional directory containing reference ROOT files for KS comparison. "
            "Expected filename: <DETECTOR>_<validation>_particleGun_hist.root"
        ),
    )
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(True)

    with open(args.style_config, "r") as f:
        plotting_cfg = yaml.safe_load(f)

    with open(args.detector_config, "r") as f:
        det_cfg = yaml.safe_load(f)

    detector_name = det_cfg.get("detector", "UNKNOWN")
    variant_name = det_cfg.get("version", "default")
    validation_name = det_cfg.get("validation", "general")

    validation_slug = normalize_slug(validation_name)

    # Parse input files: validation_name=path
    file_map = {}
    for item in args.inputs:
        if "=" in item:
            key, path = item.split("=", 1)
            file_map[key] = path
        else:
            logger.warning(f"Skipping malformed --inputs entry (expected key=path): {item!r}")

    if not file_map:
        logger.error("No valid input files parsed from --inputs. Aborting.")
        sys.exit(1)

    hist_registries = {key: read_histograms_from_file(path) for key, path in file_map.items()}

    # Load reference histograms when a reference directory is provided.
    # Expected filename convention: <DETECTOR>_<validation>_particleGun_hist.root
    ref_registries = {}
    if args.ref_dir and os.path.exists(args.ref_dir):
        for key in file_map:
            ref_path = os.path.join(
                args.ref_dir, f"{detector_name}_{key}_particleGun_hist.root"
            )
            if os.path.exists(ref_path):
                ref_registries[key] = read_histograms_from_file(ref_path)
                logger.info(f"Loaded reference histograms for '{key}' from: {ref_path}")
            else:
                logger.warning(f"No reference file found for '{key}' at: {ref_path}")
    elif args.ref_dir:
        logger.warning(f"Reference directory does not exist: {args.ref_dir}")

    track_collections = det_cfg.get("collections", {}).get("track_collections", [])

    # Build flat list of (histogram_key, title, system) from plot specs in config
    plot_specs = _resolve_plot_specs(det_cfg.get("plots", []), track_collections)

    plot_count = 0
    for ds_key, registry in hist_registries.items():
        ref_registry = ref_registries.get(ds_key, {})

        for spec in plot_specs:
            histogram = find_histogram(registry, ds_key, spec["key"])
            if not histogram:
                logger.debug(f"Histogram '{spec['key']}' not found in registry for '{ds_key}', skipping.")
                continue

            ref_histogram = find_histogram(ref_registry, ds_key, spec["key"]) if ref_registry else None

            # Detector and variant directory names intentionally match config and
            # workarea names so downstream web/pipeline stages read the same tree.
            target_dir = os.path.join(
                args.output_dir,
                detector_name,
                variant_name,
                validation_slug,
                normalize_slug(spec["system"]),
            )

            generate_plot(
                hist=histogram,
                ref_hist=ref_histogram,
                filename=f"{spec['key']}.png",
                out_dir=target_dir,
                config=plotting_cfg,
                title=f"{detector_name} — {spec['title']}",
            )
            plot_count += 1

    logger.info(f"Plotting complete. Saved {plot_count} plot(s) under '{args.output_dir}'.")


def _resolve_plot_specs(plots_config: list, track_collections: list) -> list:
    """Expands plot definitions into a flat list of (key, title, system) dicts.

    Per-collection plots are expanded once for each track collection.
    """
    specs = []
    for plot in plots_config:
        system = plot.get("system", plot.get("subdetector", "general"))
        if plot.get("per_collection"):
            for col in track_collections:
                specs.append({
                    "key": f"{plot['key']}_{col}",
                    "title": f"{plot['title']} ({col})",
                    "system": system,
                })
        else:
            specs.append({
                "key": plot["key"],
                "title": plot["title"],
                "system": system,
            })
    return specs


if __name__ == "__main__":
    main()
