#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

IGNORED_CONFIG_FILENAMES = {"plotting.yaml", "web.yaml"}
TSV_COLUMNS = [
    "detector",
    "version",
    "slug",
    "validation",
    "config_path",
    "config_dir",
    "config_rel_dir",
    "particle",
    "output_tag",
    "energy",
    "seed",
    "sim_script",
    "hist_script",
]


def parse_requested_versions(raw: Optional[str]) -> Optional[set[str]]:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned.lower() in {"all", "*"}:
        return None
    return {item.strip() for item in cleaned.split(",") if item.strip()}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


def iter_config_paths(repo_root: Path):
    config_root = repo_root / "config"
    if not config_root.is_dir():
        return

    for detector_dir in sorted(p for p in config_root.iterdir() if p.is_dir()):
        for version_dir in sorted(p for p in detector_dir.iterdir() if p.is_dir()):
            for cfg_path in sorted(version_dir.glob("*.yaml")):
                if cfg_path.name in IGNORED_CONFIG_FILENAMES:
                    continue
                yield cfg_path


def resolve_required_simulation_field(cfg_path: Path, cfg: dict, field: str) -> str:
    sim_cfg = cfg.get("simulation") or {}
    value = sim_cfg.get(field)
    if value is None or str(value).strip() == "":
        raise ValueError(
            f"Config '{cfg_path}' is missing required simulation.{field}"
        )
    return str(value)


def version_selected(
    detector: str, version: str, requested_versions: Optional[set[str]]
) -> bool:
    if requested_versions is None:
        return True
    variant_path = f"{detector}/{version}"
    return version in requested_versions or variant_path in requested_versions


def discover_validation_flows(
    repo_root: Path, versions_raw: Optional[str] = None
) -> list[dict]:
    requested_versions = parse_requested_versions(versions_raw)
    flows: list[dict] = []

    for cfg_path in iter_config_paths(repo_root):
        detector_from_path = cfg_path.parent.parent.name
        version_from_path = cfg_path.parent.name
        cfg = load_yaml(cfg_path)

        detector = str(cfg.get("detector", detector_from_path))
        version = str(cfg.get("version", version_from_path))
        validation = str(cfg.get("validation", cfg_path.stem))
        slug = version

        if not version_selected(detector, version, requested_versions):
            continue

        variant_script_dir = repo_root / "scripts" / "detectors" / detector / version
        sim_script = variant_script_dir / "sim_digi.sh"
        hist_script = variant_script_dir / "hist.py"

        if not sim_script.is_file():
            raise FileNotFoundError(
                f"Missing sim_digi.sh for config '{cfg_path}' at '{sim_script}'"
            )
        if not hist_script.is_file():
            raise FileNotFoundError(
                f"Missing hist.py for config '{cfg_path}' at '{hist_script}'"
            )

        particle = resolve_required_simulation_field(cfg_path, cfg, "particle")
        output_tag = resolve_required_simulation_field(cfg_path, cfg, "output_tag")
        energy = resolve_required_simulation_field(cfg_path, cfg, "energy")
        seed = str((cfg.get("simulation") or {}).get("seed", 42))

        flows.append(
            {
                "detector": detector,
                "version": version,
                "slug": slug,
                "validation": validation,
                "config_path": str(cfg_path),
                "config_dir": str(cfg_path.parent),
                "config_rel_dir": f"config/{detector}/{version}",
                "particle": particle,
                "output_tag": output_tag,
                "energy": energy,
                "seed": seed,
                "sim_script": str(sim_script),
                "hist_script": str(hist_script),
            }
        )

    return flows


def read_tsv_manifest(manifest_path: Path) -> list[dict]:
    flows: list[dict] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            values = line.split("\t")
            if len(values) != len(TSV_COLUMNS):
                raise ValueError(
                    f"Manifest '{manifest_path}' has {len(values)} fields on line '{line}', expected {len(TSV_COLUMNS)}"
                )
            flows.append(dict(zip(TSV_COLUMNS, values)))
    return flows


def discover_detector_variants(
    flows: list[dict], base_web_config: Optional[dict] = None
) -> list[dict]:
    base_web_config = base_web_config or {}
    configured = {}
    for det in base_web_config.get("detectors", []):
        configured[(det.get("id"), det.get("version"))] = det
        configured.setdefault((det.get("id"), None), det)

    variants: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for flow in flows:
        key = (flow["detector"], flow["version"])
        if key in seen:
            continue
        seen.add(key)

        override = configured.get(key) or configured.get((flow["detector"], None), {})
        variants.append(
            {
                "id": flow["detector"],
                "slug": flow["slug"],
                "version": flow["version"],
                "name": override.get("name", f"{flow['detector']} Detector"),
                "description": override.get(
                    "description",
                    f"Validation plots for {flow['detector']} {flow['version']}",
                ),
                "config_dir": flow["config_rel_dir"],
            }
        )

    variants.sort(key=lambda item: (item["id"], item["version"]))
    return variants


def write_tsv(flows: list[dict], output_path: Path):
    with output_path.open("w", encoding="utf-8") as handle:
        for flow in flows:
            handle.write("\t".join(flow[column] for column in TSV_COLUMNS))
            handle.write("\n")


def write_generated_web_config(
    flows: list[dict], base_web_config_path: Path, output_path: Path
):
    base_cfg = load_yaml(base_web_config_path) if base_web_config_path.is_file() else {}
    generated = {key: value for key, value in base_cfg.items() if key != "detectors"}
    generated["detectors"] = discover_detector_variants(flows, base_cfg)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(generated, handle, sort_keys=False)


def main():
    parser = argparse.ArgumentParser(
        description="Discover validation flows from the repository config tree or from an existing manifest."
    )
    parser.add_argument("--repo-root", help="Repository root directory")
    parser.add_argument(
        "--manifest",
        help="Existing TSV validation flow manifest to read instead of re-discovering from config/",
    )
    parser.add_argument(
        "--versions",
        default="",
        help=(
            "Optional comma-separated detector variants to include. "
            "Empty, all, or * means discover everything."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "tsv"],
        default="json",
        help="Output format for discovered validation flows",
    )
    parser.add_argument("--output", help="Optional file to write the discovered flows to")
    parser.add_argument(
        "--generate-web-config",
        help="Optional path to write a generated web config YAML",
    )
    parser.add_argument(
        "--base-web-config",
        default="",
        help="Optional base web config YAML with branding and detector metadata overrides",
    )
    args = parser.parse_args()

    try:
        if args.manifest:
            flows = read_tsv_manifest(Path(args.manifest).resolve())
        else:
            if not args.repo_root:
                print("ERROR: --repo-root is required unless --manifest is provided.", file=sys.stderr)
                sys.exit(1)
            repo_root = Path(args.repo_root).resolve()
            flows = discover_validation_flows(repo_root, args.versions)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not flows:
        print("ERROR: No validation flows discovered.", file=sys.stderr)
        sys.exit(1)

    if args.generate_web_config:
        write_generated_web_config(
            flows,
            Path(args.base_web_config).resolve() if args.base_web_config else Path(),
            Path(args.generate_web_config).resolve(),
        )

    if args.format == "json":
        rendered = json.dumps(flows, indent=2)
        if args.output:
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
    else:
        if not args.output:
            print(
                "ERROR: --output is required when --format tsv is used.",
                file=sys.stderr,
            )
            sys.exit(1)
        write_tsv(flows, Path(args.output).resolve())


if __name__ == "__main__":
    main()
