"""PyTerametrics - Python port of TerraMetrics IaC quality metrics for Terraform HCL files."""

__version__ = "0.1.1"

from pyterametrics.analyzer import analyze_file, analyze_directory
from pyterametrics.metrics import collect_all_metrics
