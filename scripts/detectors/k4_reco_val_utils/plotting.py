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

from detectors.k4_reco_val_utils.helpers import clear_directory
from detectors.k4_reco_val_utils.io import read_histograms_from_file
from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("plotting")


def find_histogram(registry, dataset_key, plot_key):
    """Flexible key search handling both raw keys and prefixed names (e.g. h_electron_<key>)."""
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


def get_accepted_events(hist):
    """Extracts accepted_events metadata from Python attributes or ROOT GetListOfFunctions()."""
    if not hist:
        return 0
    if hasattr(hist, "accepted_events") and hist.accepted_events > 0:
        return hist.accepted_events
    if hasattr(hist, "GetListOfFunctions"):
        funcs = hist.GetListOfFunctions()
        if funcs:
            obj = funcs.FindObject("accepted_events")
            if obj:
                try:
                    val = int(obj.GetTitle())
                    hist.accepted_events = val
                    return val
                except (ValueError, TypeError):
                    pass
    return getattr(hist, "accepted_events", 0)


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
    """Formats numeric axis divisions and integer labels cleanly without forcing alphanumeric string mode."""
    x_axis = hist.GetXaxis()
    y_axis = hist.GetYaxis()

    x_axis.SetNdivisions(510, ROOT.kTRUE)
    y_axis.SetNdivisions(510, ROOT.kTRUE)

    if hist.InheritsFrom("TH1I") or isinstance(hist, ROOT.TH1I):
        x_axis.SetDecimals(ROOT.kFALSE)


def draw_title_latex(title_text, canvas):
    """Draws pad title via TLatex, dynamically scaling font size for long text strings."""
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


def generate_standalone_plot(
    hist,
    filename,
    out_dir,
    style_cfg,
    draw_opt="HIST",
    title=None,
    line_color=None,
    line_style=1,
    canvas_dims=None,
):
    apply_root_graphics_style(style_cfg)
    full_path = os.path.join(out_dir, filename)
    os.makedirs(out_dir, exist_ok=True)

    if line_color is None:
        line_color = ROOT.TColor.GetColor("#0072B2")

    c_width, c_height = canvas_dims if canvas_dims else [800, 600]
    canvas = ROOT.TCanvas(
        f"c_{hist.GetName()}_{int(time.time()*1000)%1000}", "", c_width, c_height
    )
    is_2d = isinstance(hist, ROOT.TH2)
    if is_2d:
        canvas.SetRightMargin(0.15)
        if draw_opt == "HIST":
            draw_opt = "COLZ"

    if not is_2d:
        hist.SetLineColor(line_color)
        hist.SetLineStyle(line_style)
        hist.SetLineWidth(style_cfg.get("line_width", 3))

    hist.GetXaxis().SetTitleSize(style_cfg.get("title_size", 0.055))
    hist.GetYaxis().SetTitleSize(style_cfg.get("title_size", 0.055))
    hist.GetXaxis().SetLabelSize(style_cfg.get("label_size", 0.045))
    hist.GetYaxis().SetLabelSize(style_cfg.get("label_size", 0.045))
    hist.GetXaxis().SetTitleOffset(1.1)
    hist.GetYaxis().SetTitleOffset(1.3)

    hist.Draw(draw_opt)
    optimize_axis_ticks(hist)

    n_ev = get_accepted_events(hist)
    full_title = f"{title}  (N_{{ev}} = {n_ev})" if title else ""
    latex = draw_title_latex(full_title, canvas)
    if latex:
        canvas._tracked = [latex]

    canvas.SaveAs(full_path)
    logger.debug(f"Saved standalone plot: {full_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Shared detector-agnostic plotting engine."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input ROOT histogram files in key=path format (e.g. electron=idea_e.root muon=idea_mu.root)",
    )
    parser.add_argument(
        "--detector-config",
        required=True,
        help="Detector configuration specifying plot lists",
    )
    parser.add_argument(
        "--style-config",
        default="config/plotting.yaml",
        help="Global visual style configuration",
    )
    parser.add_argument(
        "--output-dir", default="plots", help="Output directory for rendered plots"
    )
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(True)

    logger.info("Starting plotting script execution.")
    logger.info(f"Detector config: {args.detector_config}")
    logger.info(f"Style config:    {args.style_config}")
    logger.info(f"Output directory:{args.output_dir}")

    try:
        with open(args.style_config, "r") as f:
            style_cfg = yaml.safe_load(f)
        logger.debug("Style configuration YAML loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load style configuration '{args.style_config}': {e}")
        sys.exit(1)

    try:
        with open(args.detector_config, "r") as f:
            det_cfg = yaml.safe_load(f)
        logger.debug("Detector configuration YAML loaded successfully.")
    except Exception as e:
        logger.error(
            f"Failed to load detector configuration '{args.detector_config}': {e}"
        )
        sys.exit(1)

    file_map = {}
    for item in args.inputs:
        if "=" in item:
            k, v = item.split("=", 1)
            file_map[k] = v
        else:
            logger.error(f"Input entry '{item}' not in key=path format.")
            sys.exit(1)

    logger.info(f"Processing {len(file_map)} input dataset(s): {list(file_map.keys())}")

    hist_registries = {}
    for k, v in file_map.items():
        logger.info(f"Reading ROOT histogram file for dataset key '{k}': {v}")
        reg = read_histograms_from_file(v)
        hist_registries[k] = reg
        logger.info(
            f"Dataset '{k}': Loaded {len(reg)} histogram key(s). Keys: {list(reg.keys())}"
        )

    logger.debug(f"Clearing output directory: {args.output_dir}")
    clear_directory(args.output_dir)

    track_collections = det_cfg.get("collections", {}).get("track_collections", [])
    plot_specs = []
    for plot in det_cfg.get("plots", []):
        system = plot.get("system", plot.get("subdetector", "general"))
        technology = plot.get("technology", plot.get("algorithm", "general"))
        region = plot.get("region", plot.get("module_type", "general"))
        signal_type = plot.get("signal_type", None)

        if plot.get("per_collection"):
            for col in track_collections:
                plot_specs.append(
                    {
                        "key": f"{plot['key']}_{col}",
                        "title": f"{plot['title']} ({col})",
                        "system": system,
                        "technology": technology,
                        "region": region,
                        "signal_type": signal_type,
                    }
                )
        else:
            plot_specs.append(
                {
                    "key": plot["key"],
                    "title": plot["title"],
                    "system": system,
                    "technology": technology,
                    "region": region,
                    "signal_type": signal_type,
                }
            )

    logger.info(
        f"Targeting {len(plot_specs)} plot specification(s) from detector config."
    )

    canvas_dims = style_cfg.get("canvas_dimensions", [800, 600])
    style_opts = style_cfg.get("style", {})

    standalone_count = 0

    logger.info("Generating categorized standalone visualizations...")
    for ds_key, registry in hist_registries.items():
        sample_style = style_cfg.get("sample_styles", {}).get(ds_key, {})
        color = ROOT.TColor.GetColor(sample_style.get("color", "#0072B2"))
        style = sample_style.get("style", 1)

        for spec in plot_specs:
            key = spec["key"]
            histogram = find_histogram(registry, ds_key, key)
            if histogram:
                # Structure: <output-dir>/<particle>/<system>/<technology>/<region>[/<signal_type>]/<key>.png
                path_parts = [
                    ds_key,
                    spec["system"],
                    spec["technology"],
                    spec["region"],
                ]
                if spec["signal_type"]:
                    path_parts.append(spec["signal_type"])

                target_subpath = os.path.join(*path_parts)
                target_dir = os.path.join(args.output_dir, target_subpath)

                generate_standalone_plot(
                    hist=histogram,
                    filename=f"{key}.png",
                    out_dir=target_dir,
                    style_cfg=style_opts,
                    draw_opt="COLZ" if isinstance(histogram, ROOT.TH2) else "HIST",
                    title=f"{ds_key.capitalize()} - {spec['title']}",
                    line_color=color,
                    line_style=style,
                    canvas_dims=canvas_dims,
                )
                standalone_count += 1
            else:
                logger.warning(
                    f"Plot key '{key}' not found in registry for dataset '{ds_key}'. Skipping."
                )

    logger.info(
        f"Plotting completed successfully. Created {standalone_count} plot(s) in subdirectories."
    )


if __name__ == "__main__":
    main()
