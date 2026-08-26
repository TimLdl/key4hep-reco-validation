#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


# GitLab CI rule `if` expressions must be single-quoted in YAML so that the
# dollar sign and embedded double-quotes are preserved literally.
class _SingleQuoted(str):
    pass


def _single_quoted_representer(dumper: yaml.Dumper, value: "_SingleQuoted") -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="'")


yaml.add_representer(_SingleQuoted, _single_quoted_representer)
yaml.add_representer(  # also register for SafeDumper used by safe_dump
    _SingleQuoted,
    _single_quoted_representer,
    Dumper=yaml.SafeDumper,
)

from config_discovery import discover_validation_flows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a child pipeline with one independent DAG chain per validation workflow."
    )
    parser.add_argument("--repo-root", required=True, help="Repository root path")
    parser.add_argument(
        "--versions",
        default="",
        help="Optional variant filter (same semantics as setup/config_discovery)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for generated child pipeline YAML",
    )
    parser.add_argument(
        "--max-shards",
        type=int,
        default=0,
        help="Optional upper bound for workflow DAG chains (0 means no cap).",
    )
    return parser.parse_args()


def stage_job_template() -> dict:
    return {
        "image": "gitlab-registry.cern.ch/key4hep/k4-deploy/alma9-build",
        "tags": ["validation"],
        "before_script": ['export WORKAREA="${WORKAREA:-${CI_PROJECT_DIR}/validation}"'],
    }


def stage_job_base() -> dict:
    """Common fields inlined into every concrete job for reliable runner matching."""
    return {
        "image": "gitlab-registry.cern.ch/key4hep/k4-deploy/alma9-build",
        "tags": ["validation"],
    }


def stage_job_script(script_name: str) -> list[str]:
    return [f"bash scripts/k4_reco_val_pipeline_utils/{script_name}"]


def artifact_def() -> dict:
    return {"when": "always", "paths": ["validation/"]}


def build_child_pipeline(chain_count: int) -> dict:
    pipeline = {
        "stages": ["setup", "simulation", "validation", "plot", "gate", "web", "cleanup"],
        ".template-job": stage_job_template(),
        "setup": {
            **stage_job_base(),
            "extends": ".template-job",
            "stage": "setup",
            "when": "always",
            "script": stage_job_script("setup.sh"),
            "artifacts": artifact_def(),
        },
    }

    plot_jobs: list[str] = []
    for shard_index in range(chain_count):
        shard_name = f"{shard_index + 1:03d}-of-{chain_count:03d}"
        sim_job = f"sim-{shard_name}"
        val_job = f"val-{shard_name}"
        plot_job = f"plot-{shard_name}"
        plot_jobs.append(plot_job)

        shard_vars = {
            "FLOW_SHARD_TOTAL": str(chain_count),
            "FLOW_SHARD_INDEX": str(shard_index),
            "SOFT_FAIL_ON_EMPTY_SHARD": "true",
            "SUPPRESS_SHARD_MAILS": "true",
        }

        pipeline[sim_job] = {
            **stage_job_base(),
            "extends": ".template-job",
            "stage": "simulation",
            "needs": [{"job": "setup", "artifacts": True}],
            "variables": dict(shard_vars),
            "script": stage_job_script("simulation.sh"),
            "artifacts": artifact_def(),
        }
        pipeline[val_job] = {
            **stage_job_base(),
            "extends": ".template-job",
            "stage": "validation",
            "needs": [{"job": sim_job, "artifacts": True}],
            "variables": dict(shard_vars),
            "script": stage_job_script("validation.sh"),
            "artifacts": artifact_def(),
        }
        pipeline[plot_job] = {
            **stage_job_base(),
            "extends": ".template-job",
            "stage": "plot",
            "needs": [{"job": val_job, "artifacts": True}],
            "variables": dict(shard_vars),
            "rules": [
                {"if": _SingleQuoted('$MAKE_REFERENCE_SAMPLE == "yes"'), "when": "never"},
                {"when": "on_success"},
            ],
            "script": stage_job_script("plot.sh"),
            "artifacts": artifact_def(),
        }

    web_needs = [{"job": job_name, "artifacts": True} for job_name in plot_jobs]
    pipeline["workflow-gate"] = {
        **stage_job_base(),
        "extends": ".template-job",
        "stage": "gate",
        "rules": [
            {"if": _SingleQuoted('$MAKE_REFERENCE_SAMPLE == "yes"'), "when": "never"},
            {"when": "on_success"},
        ],
        "needs": web_needs,
        "script": stage_job_script("workflow_gate.sh"),
        "artifacts": artifact_def(),
    }
    pipeline["web"] = {
        **stage_job_base(),
        "extends": ".template-job",
        "stage": "web",
        "when": "on_success",
        "rules": [
            {"if": _SingleQuoted('$MAKE_REFERENCE_SAMPLE == "yes"'), "when": "never"},
            {"when": "on_success"},
        ],
        "needs": [{"job": "workflow-gate", "artifacts": True}],
        "script": stage_job_script("web.sh"),
        "artifacts": artifact_def(),
    }
    pipeline["cleanup"] = {
        **stage_job_base(),
        "extends": ".template-job",
        "stage": "cleanup",
        "when": "always",
        "script": stage_job_script("cleanup.sh"),
    }
    return pipeline


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_path = Path(args.output).resolve()

    flows = discover_validation_flows(repo_root, args.versions)
    flow_count = len(flows)
    if flow_count == 0:
        print(
            "ERROR: No validation workflows discovered; cannot generate dynamic pipeline.",
            file=sys.stderr,
        )
        return 1

    chain_count = flow_count
    if args.max_shards and args.max_shards > 0:
        chain_count = min(chain_count, args.max_shards)

    pipeline = build_child_pipeline(chain_count)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(pipeline, handle, sort_keys=False)

    print(f"Discovered workflows: {flow_count}")
    print(f"Configured workflow chains: {chain_count}")
    print(f"Generated child pipeline: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
