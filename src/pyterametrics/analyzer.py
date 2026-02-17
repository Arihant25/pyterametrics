"""File and directory analysis orchestration.

Replaces Java's FileLevelMetricsCalculator, BlockDivider, LocalAnalyzer,
DistantAnalyzer, RepoAnalyzer, and DirAnalyzerService.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from pyterametrics.parser import parse_hcl_file, parse_hcl_string
from pyterametrics.ast_walker import (
    find_top_blocks,
    get_block_type,
    get_block_labels,
    get_block_line_range,
    get_block_content,
)
from pyterametrics.metrics import collect_all_metrics


def analyze_block(block, file_content: str) -> Dict[str, Any]:
    """Analyze a single HCL block and return its metrics.

    Args:
        block: Lark Tree node for the block.
        file_content: Full file content for line extraction.

    Returns:
        Dict of metrics for the block.
    """
    start, end = get_block_line_range(block)
    content = get_block_content(file_content, start, end)
    return collect_all_metrics(block, content)


def analyze_file(filepath: str, target: Optional[str] = None) -> Dict[str, Any]:
    """Analyze a single Terraform file and return metrics for all blocks.

    Equivalent to Java's FileCommand + FileLevelMetricsCalculator.

    Args:
        filepath: Path to the .tf file.
        target: Optional output file path to write JSON results.

    Returns:
        Dict containing file-level metrics and block-level metrics.
    """
    filepath = str(Path(filepath).resolve())
    file_content = Path(filepath).read_text(encoding="utf-8", errors="replace")

    try:
        tree = parse_hcl_string(file_content)
    except Exception as e:
        return {
            "file": filepath,
            "status": "error",
            "error": str(e),
            "blocks": [],
        }

    blocks = find_top_blocks(tree)
    block_metrics = []

    for block in blocks:
        try:
            metrics = analyze_block(block, file_content)
            metrics["file"] = filepath
            block_metrics.append(metrics)
        except Exception as e:
            block_metrics.append({
                "file": filepath,
                "block": get_block_type(block),
                "error": str(e),
            })

    result = {
        "file": filepath,
        "status": "success",
        "num_blocks": len(block_metrics),
        "blocks": block_metrics,
    }

    if target:
        _write_json(result, target)

    return result


def analyze_directory(
    directory: str,
    project_name: str = "",
    target: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze all .tf files in a directory.

    Equivalent to Java's DirCommand + LocalAnalyzer.

    Args:
        directory: Path to the directory containing .tf files.
        project_name: Name of the project for labeling.
        target: Optional output directory for JSON results.

    Returns:
        Dict with aggregated metrics.
    """
    directory = str(Path(directory).resolve())
    tf_files = _find_tf_files(directory)

    all_blocks = []
    for tf_file in tf_files:
        result = analyze_file(tf_file)
        if result.get("status") == "success":
            all_blocks.extend(result["blocks"])

    output = {
        "project": project_name or Path(directory).name,
        "directory": directory,
        "num_files": len(tf_files),
        "num_blocks": len(all_blocks),
        "blocks": all_blocks,
    }

    if target:
        target_path = os.path.join(target, f"{output['project']}.json")
        _write_json(output, target_path)

    return output


def _find_tf_files(directory: str) -> List[str]:
    """Recursively find all .tf files in a directory."""
    tf_files = []
    for root, dirs, files in os.walk(directory):
        for f in sorted(files):
            if f.endswith(".tf"):
                tf_files.append(os.path.join(root, f))
    return tf_files


def _write_json(data: Any, filepath: str) -> None:
    """Write data to a JSON file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
