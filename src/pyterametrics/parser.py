"""HCL2 file parsing using python-hcl2's internal Lark parser.

This module provides access to the full Lark parse tree (not just the dict
conversion), which is required for deep expression-level analysis.
"""

from pathlib import Path
from hcl2.parser import reconstruction_parser


def _get_parser():
    """Get the cached Lark parser instance."""
    return reconstruction_parser()


def parse_hcl_file(filepath: str) -> "lark.Tree":
    """Parse an HCL file and return the Lark parse tree.

    Args:
        filepath: Path to the .tf file.

    Returns:
        Lark Tree representing the parsed HCL.
    """
    content = Path(filepath).read_text(encoding="utf-8", errors="replace")
    return parse_hcl_string(content)


def parse_hcl_string(content: str) -> "lark.Tree":
    """Parse an HCL string and return the Lark parse tree.

    Args:
        content: HCL content string.

    Returns:
        Lark Tree representing the parsed HCL.
    """
    parser = _get_parser()
    # python-hcl2 requires content to end with newline
    if not content.endswith("\n"):
        content += "\n"
    return parser.parse(content)
