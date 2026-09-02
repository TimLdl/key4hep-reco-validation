import os
import shutil
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("web_builder")

# Map folder/particle aliases to clean display names & slugs
PARTICLE_MAP = {
    "electron": "Electron",
    "electrons": "Electron",
    "e": "Electron",
    "e-": "Electron",
    "e+": "Electron",
    "muon": "Muon",
    "muons": "Muon",
    "mu": "Muon",
    "mu-": "Muon",
    "mu+": "Muon",
    "photon": "Photon",
    "photons": "Photon",
    "gamma": "Photon",
    "pion": "Pion",
    "pions": "Pion",
    "pi": "Pion",
    "charged_pion": "Charged Pion",
    "neutral_pion": "Neutral Pion",
    "pi0": "Neutral Pion",
    "pipm": "Charged Pion",
    "kaon": "Kaon",
    "kaons": "Kaon",
    "k": "Kaon",
    "proton": "Proton",
    "protons": "Proton",
    "p": "Proton",
    "jet": "Jet",
    "jets": "Jet",
    "tau": "Tau",
    "taus": "Tau",
}


class WebBuilder:
    """Engine for parsing validation plot hierarchies and rendering particle-specific web dashboards."""

    def __init__(
        self,
        web_config: dict,
        templates_dir: Path,
        static_dir: Path,
        plots_dir: Path,
        output_dir: Path,
    ):
        self.cfg = web_config
        self.templates_dir = Path(templates_dir)
        self.static_dir = Path(static_dir)
        self.plots_dir = Path(plots_dir)
        self.output_dir = Path(output_dir)

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _clean_directory_contents(self, target_dir: Path):
        """Safely unlinks deployment files avoiding EOS FUSE locking issues."""
        if not target_dir.exists():
            return
        for item in target_dir.iterdir():
            if item.is_dir() and not item.is_symlink():
                self._clean_directory_contents(item)
                try:
                    item.rmdir()
                except OSError:
                    pass
            else:
                try:
                    item.unlink(missing_ok=True)
                except OSError:
                    pass

    def _clean_deploy_directory(self):
        """Wipes deployment output directory prior to site generation."""
        if self.output_dir.exists():
            logger.info(f"Cleaning deployment directory '{self.output_dir}'...")
            self._clean_directory_contents(self.output_dir)

    def _copy_static_assets(self):
        """Copies static assets (CSS, JS, images) to output destination."""
        target_static = self.output_dir / "static"
        target_static.mkdir(parents=True, exist_ok=True)

        resolved_static = self.static_dir.resolve()

        if resolved_static.exists():
            shutil.copytree(resolved_static, target_static, dirs_exist_ok=True)
            logger.info(
                f"Copied static web assets from '{resolved_static}' to '{target_static}'"
            )
        else:
            logger.error(f"Static directory NOT FOUND at: '{resolved_static}'")

    def _parse_plot_metadata(self, img_path: Path, detector_root: Path) -> dict:
        """Parses particle, subdetector, algorithm, and module type dynamically regardless of depth."""
        try:
            rel_path = img_path.relative_to(detector_root)
            dir_parts = [p.lower() for p in rel_path.parts[:-1]]
        except ValueError:
            dir_parts = []

        particle_display = "General"
        particle_slug = "general"
        subdetector_display = "General"
        algorithm_display = "General"
        module_type_display = "General"

        # Dynamically locate which directory level contains a particle name
        p_idx = -1
        for idx, part in enumerate(dir_parts):
            if part in PARTICLE_MAP:
                p_idx = idx
                particle_slug = part
                particle_display = PARTICLE_MAP[part]
                break

        if p_idx != -1:
            # Hierarchy relative to particle folder position:
            # dir_parts[p_idx + 1] -> Subdetector (e.g., calorimetry)
            # dir_parts[p_idx + 2] -> Algorithm (e.g., dual_readout / lar_calorimeter)
            # dir_parts[p_idx + 3] -> Module/Region (e.g., cherenkov / barrel)
            if p_idx + 1 < len(dir_parts):
                subdetector_display = dir_parts[p_idx + 1].replace("_", " ").title()
            if p_idx + 2 < len(dir_parts):
                algorithm_display = dir_parts[p_idx + 2].replace("_", " ").title()
            if p_idx + 3 < len(dir_parts):
                module_type_display = dir_parts[p_idx + 3].replace("_", " ").title()
        else:
            # Fallback if particle is not a dedicated parent directory
            full_str = str(rel_path).lower()
            for p_key, p_name in PARTICLE_MAP.items():
                if p_key in full_str:
                    particle_slug = p_key
                    particle_display = p_name
                    break

            # Filter out detector version wrappers like IDEA_o1_v03
            clean_parts = [
                p
                for p in dir_parts
                if not ("_o" in p or "_v" in p or "allegro" in p or "idea" in p)
            ]
            if len(clean_parts) >= 1:
                subdetector_display = clean_parts[0].replace("_", " ").title()
            if len(clean_parts) >= 2:
                algorithm_display = clean_parts[1].replace("_", " ").title()
            if len(clean_parts) >= 3:
                module_type_display = clean_parts[2].replace("_", " ").title()

        clean_title = img_path.stem.replace("_", " ").title()

        s_slug = subdetector_display.lower().replace(" ", "_")
        a_slug = algorithm_display.lower().replace(" ", "_")
        m_slug = module_type_display.lower().replace(" ", "_")

        return {
            "file_path": img_path,
            "filename": img_path.name,
            "title": clean_title,
            "particle": particle_display,
            "particle_slug": particle_slug,
            "subdetector": subdetector_display,
            "algorithm": algorithm_display,
            "module_type": module_type_display,
            "subpath_slugs": (s_slug, a_slug, m_slug),
            "rel_subpath": rel_path,
        }

    def _collect_and_group_detector_plots(
        self, detector_id: str, detector_version: str
    ) -> dict:
        detector_dir = self.plots_dir / detector_id
        grouped_particles = {}
        discovered_paths = set()

        if detector_dir.exists():
            for img_path in sorted(detector_dir.rglob("*.png")):
                try:
                    rel_path = img_path.relative_to(detector_dir)
                except ValueError:
                    continue

                if rel_path in discovered_paths:
                    continue
                discovered_paths.add(rel_path)

                meta = self._parse_plot_metadata(img_path, detector_dir)
                p_slug = meta["particle_slug"]
                s_slug, a_slug, m_slug = meta["subpath_slugs"]

                # Output path: detectors/<det_id>/<particle>/plots/<subdet>/<algo>/<module>/<filename>.png
                dest_img_dir = (
                    self.output_dir
                    / "detectors"
                    / detector_id
                    / p_slug
                    / "plots"
                    / s_slug
                    / a_slug
                    / m_slug
                )
                dest_img_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(img_path, dest_img_dir / img_path.name)

                meta["web_path"] = f"plots/{s_slug}/{a_slug}/{m_slug}/{img_path.name}"

                if p_slug not in grouped_particles:
                    grouped_particles[p_slug] = {
                        "name": meta["particle"],
                        "slug": p_slug,
                        "tree": {},
                        "count": 0,
                    }

                particle_tree = grouped_particles[p_slug]["tree"]
                s_det = meta["subdetector"]
                algo = meta["algorithm"]
                mod = meta["module_type"]

                particle_tree.setdefault(s_det, {}).setdefault(algo, {}).setdefault(
                    mod, []
                ).append(meta)
                grouped_particles[p_slug]["count"] += 1

        logger.info(
            f"[{detector_id}] Grouped {len(discovered_paths)} plot(s) into separate particle dashboards: "
            f"{list(grouped_particles.keys())}"
        )
        return grouped_particles

    def render_page(self, template_name: str, relative_output_path: str, context: dict):
        """Renders a Jinja2 template and forces EOS storage disk flushing."""
        template = self.jinja_env.get_template(template_name)
        rendered_content = template.render(**context)

        out_path = self.output_dir / relative_output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered_content)
            f.flush()
            os.fsync(f.fileno())

        logger.debug(f"Rendered HTML written to: {out_path}")

    def build(self):
        """Main execution workflow for building the validation site."""
        logger.info("Starting website build sequence...")
        self._clean_deploy_directory()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._copy_static_assets()

        site_title = self.cfg.get("site_title", "Key4hep Validation")
        detectors = self.cfg.get("detectors", [])

        for det in detectors:
            det_id = det.get("id")
            det_version = det.get("version", "default")
            particles_data = self._collect_and_group_detector_plots(det_id, det_version)

            det["particles"] = [
                {"name": data["name"], "slug": data["slug"], "count": data["count"]}
                for data in particles_data.values()
            ]

            # 1. Detector Landing Page
            det_context = {
                "site_title": site_title,
                "config": self.cfg,
                "detector": det,
                "detectors": detectors,
                "particles_data": particles_data,
                "active_page": det_id,
                "root_rel": "../../",
            }
            self.render_page(
                template_name="detector.html.j2",
                relative_output_path=f"detectors/{det_id}/index.html",
                context=det_context,
            )

            # 2. Particle Dashboards (for each event type)
            for p_slug, p_info in particles_data.items():
                particle_context = {
                    "site_title": site_title,
                    "config": self.cfg,
                    "detector": det,
                    "detectors": detectors,
                    "current_particle": p_info,
                    "particles_list": det["particles"],
                    "tree": p_info["tree"],
                    "active_page": det_id,
                    "root_rel": "../../../",
                }
                self.render_page(
                    template_name="particle_dashboard.html.j2",
                    relative_output_path=f"detectors/{det_id}/{p_slug}/index.html",
                    context=particle_context,
                )

        # 3. Main Overview Landing Page
        index_context = {
            "site_title": site_title,
            "config": self.cfg,
            "detectors": detectors,
            "active_page": "overview",
            "root_rel": "./",
        }
        self.render_page(
            template_name="index.html.j2",
            relative_output_path="index.html",
            context=index_context,
        )

        logger.info("Website generation completed successfully.")
