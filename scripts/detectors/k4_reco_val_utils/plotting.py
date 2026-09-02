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

    is_2d = isinstance(hist, ROOT.TH2)
    if is_2d:
        canvas.SetRightMargin(canvas_cfg.get("right_margin_2d", 0.15))
        if draw_opt == "HIST":
            draw_opt = "COLZ"

    n_ev_data = get_event_count(hist)
    line_width = style_opts.get("line_width", 1)

    # Apply data styling from config
    data_style = sample_styles.get("data", {})
    data_color = parse_root_color(data_style.get("color"))
    data_line_style = data_style.get("style", 1)
    data_label = data_style.get("label", "Data")

    if not is_2d:
        hist.SetLineColor(data_color)
        hist.SetLineStyle(data_line_style)
        hist.SetLineWidth(line_width)

    legend = None
    if ref_hist:
        ref_style = sample_styles.get("reference", {})
        ref_color = parse_root_color(ref_style.get("color"))
        ref_line_style = ref_style.get("style", 1)
        ref_label = ref_style.get("label", "Reference")

        if not is_2d:
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

        # KS evaluation and bound highlighting on failure
        conf_level = ks_opts.get("confidence_level", 0.05)
        ks_res = compute_ks_test(hist, ref_hist, confidence_level=conf_level)

        if ks_res is not None and not ks_res["passed"]:
            failed_color = parse_root_color(ks_opts.get("failed_color"))
            frame_width = ks_opts.get("frame_line_width", 2)
            canvas.SetFrameLineColor(failed_color)
            canvas.SetFrameLineWidth(frame_width)

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

        legend.AddEntry(
            hist, f"{data_label} (N_{{ev}} = {n_ev_data})", "l" if not is_2d else "f"
        )
        legend.AddEntry(
            ref_hist, f"{ref_label} (N_{{ev}} = {n_ev_ref})", "l" if not is_2d else "f"
        )

        if ks_res is not None:
            status_str = "Pass" if ks_res["passed"] else "Fail"
            if ks_res["is_2d"]:
                p_x = ks_res["p_value"]["x"]
                p_y = ks_res["p_value"]["y"]
                legend.AddEntry(
                    "", f"KS p(X/Y): {p_x:.3f} / {p_y:.3f} [{status_str}]", ""
                )
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
    latex = draw_title_latex(plot_title, canvas)

    canvas.SaveAs(full_path)
    logger.debug(f"Saved plot: {full_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Shared detector-agnostic plotting engine."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input ROOT files in key=path format (e.g. data=output.root)",
    )
    parser.add_argument(
        "--detector-config",
        required=True,
        help="Detector configuration specifying plot lists and validation name",
    )
    parser.add_argument(
        "--style-config",
        default="config/plotting.yaml",
        help="Global visual style configuration",
    )
    parser.add_argument(
        "--output-dir",
        default="output/plots",
        help="Output directory for rendered plots",
    )
    parser.add_argument(
        "--ref-dir",
        default=None,
        help="Optional reference directory containing baseline ROOT files",
    )
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(True)

    with open(args.style_config, "r") as f:
        plotting_cfg = yaml.safe_load(f)

    with open(args.detector_config, "r") as f:
        det_cfg = yaml.safe_load(f)

    detector_name = det_cfg.get("detector", "ALLEGRO")
    variant_name = det_cfg.get("version", det_cfg.get("variant", "ALLEGRO_o1_v03"))
    validation_name = det_cfg.get("validation", "general")

    file_map = {}
    for item in args.inputs:
        if "=" in item:
            k, v = item.split("=", 1)
            file_map[k] = v

    hist_registries = {k: read_histograms_from_file(v) for k, v in file_map.items()}

    ref_registries = {}
    if args.ref_dir and os.path.exists(args.ref_dir):
        for k in file_map.keys():
            ref_path = os.path.join(args.ref_dir, f"{k}.root")
            if not os.path.exists(ref_path):
                ref_path = os.path.join(
                    args.ref_dir, f"{detector_name}_{k}_particleGun_hist.root"
                )
            if os.path.exists(ref_path):
                ref_registries[k] = read_histograms_from_file(ref_path)

    track_collections = det_cfg.get("collections", {}).get("track_collections", [])
    plot_specs = []
    for plot in det_cfg.get("plots", []):
        system = plot.get("system", plot.get("subdetector", "general"))
        if plot.get("per_collection"):
            for col in track_collections:
                plot_specs.append(
                    {
                        "key": f"{plot['key']}_{col}",
                        "title": f"{plot['title']} ({col})",
                        "system": system,
                    }
                )
        else:
            plot_specs.append(
                {
                    "key": plot["key"],
                    "title": plot["title"],
                    "system": system,
                }
            )

    standalone_count = 0

    for ds_key, registry in hist_registries.items():
        ref_reg = ref_registries.get(ds_key, {})

        for spec in plot_specs:
            key = spec["key"]
            histogram = find_histogram(registry, ds_key, key)
            if histogram:
                ref_histogram = (
                    find_histogram(ref_reg, ds_key, key) if ref_reg else None
                )

                target_dir = os.path.join(
                    args.output_dir,
                    detector_name,
                    variant_name,
                    validation_name,
                    spec["system"],
                )

                plot_title = f"{detector_name} - {spec['title']}"

                generate_plot(
                    hist=histogram,
                    ref_hist=ref_histogram,
                    filename=f"{key}.png",
                    out_dir=target_dir,
                    config=plotting_cfg,
                    draw_opt="COLZ" if isinstance(histogram, ROOT.TH2) else "HIST",
                    title=plot_title,
                )
                standalone_count += 1

    logger.info(
        f"Plotting completed. Saved {standalone_count} plot(s) to '{args.output_dir}'."
    )


if __name__ == "__main__":
    main()
