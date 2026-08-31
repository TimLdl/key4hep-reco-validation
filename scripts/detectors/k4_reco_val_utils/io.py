"""PODIO and ROOT I/O utilities.

Provides thin wrappers around PODIO and ROOT file operations with consistent
error handling and logging.

Functions:

- :func:`open_podio_root_reader` — opens a PODIO ROOT file for event-by-event reading
- :func:`write_histograms_to_file` — writes a histogram registry dict to a ROOT file
- :func:`read_histograms_from_file` — reads all TH1/TH2/TH3 objects from a ROOT file into a dict
"""

import os
import podio
import ROOT
from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("io_utils")


def open_podio_root_reader(file_path):
    """Opens a PODIO ROOT reader for the specified file path."""
    logger.info(f"Attempting to open PODIO ROOT file: {file_path}")
    if not os.path.exists(file_path):
        logger.error(f"Input file does not exist: {file_path}")
        return None

    try:
        reader = podio.root_io.Reader(file_path)
        logger.info(f"PODIO ROOT reader successfully established for: {file_path}")
        return reader
    except Exception as error:
        logger.error(f"Critical IO error accessing PODIO file '{file_path}': {error}")
        return None


def write_histograms_to_file(histogram_registry, output_path, mode="UPDATE"):
    """Writes a registry dictionary of ROOT histograms to a ROOT file."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.debug(f"Ensured output directory exists: {output_dir}")
        except OSError as error:
            raise OSError(
                f"Failed to create output directory '{output_dir}'"
            ) from error

    logger.info(f"Opening ROOT file for writing ({mode}): {output_path}")
    root_file = ROOT.TFile(output_path, mode)
    if not root_file or root_file.IsZombie():
        raise OSError(f"Failed to create/open ROOT file at: {output_path}")

    written_count = 0
    try:
        for key, hist in histogram_registry.items():
            if hist:
                hist.Write(hist.GetName(), ROOT.TObject.kOverwrite)
                written_count += 1
                logger.debug(
                    f"Wrote histogram '{hist.GetName()}' (registry key: '{key}')"
                )
            else:
                logger.warning(f"Skipping empty histogram for registry key: '{key}'")
    except Exception:
        logger.exception("Error occurred while writing histograms to '%s'", output_path)
        raise
    finally:
        root_file.Close()

    if written_count == 0:
        raise ValueError(f"No histograms were written to '{output_path}'")
    logger.info(f"Successfully wrote {written_count} histogram(s) to '{output_path}'")


def read_histograms_from_file(input_path):
    """Reads all TH1/TH2/TH3 histogram objects from a ROOT file into a dictionary."""
    logger.info(f"Opening ROOT file for reading: {input_path}")
    if not os.path.exists(input_path):
        logger.error(f"Histogram file does not exist: {input_path}")
        return {}

    root_file = ROOT.TFile.Open(input_path, "READ")
    if not root_file or root_file.IsZombie():
        logger.error(f"Could not open histogram ROOT file: {input_path}")
        return {}

    registry = {}
    try:
        keys = root_file.GetListOfKeys()
        if not keys:
            logger.warning(f"No object keys found in ROOT file: {input_path}")
            root_file.Close()
            return {}

        for key in keys:
            obj = key.ReadObj()
            if isinstance(obj, ROOT.TH1):
                obj.SetDirectory(0)
                obj_name = obj.GetName()
                key_name = key.GetName()
                registry[obj_name] = obj
                if key_name != obj_name:
                    registry[key_name] = obj
                logger.debug(f"Loaded histogram: '{obj_name}' (key: '{key_name}')")
    except Exception:
        logger.exception("Error reading histograms from file '%s'", input_path)
        raise
    finally:
        root_file.Close()

    logger.info(
        f"Successfully read {len(registry)} histogram key mapping(s) from '{input_path}'"
    )
    return registry
