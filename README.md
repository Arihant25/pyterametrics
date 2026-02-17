# PyTerametrics

[![PyPI version](https://badge.fury.io/py/pyterametrics.svg)](https://badge.fury.io/py/pyterametrics)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/pyterametrics.svg)](https://pypi.org/project/pyterametrics/)

Python port of [TerraMetrics](https://github.com/stilab-ets/terametrics) — IaC quality metrics for Terraform HCL files.

Computes 100+ quality metrics at the block level for Terraform `.tf` files, including:
- Cyclomatic complexity (McCabe CC)
- Lines of code / non-code lines
- Function call counts and parameters
- Conditional expressions, loops, binary operators
- Nested blocks, dynamic blocks, heredocs
- Implicit/explicit resource dependencies
- Text entropy, token statistics
- And many more...

## Installation

```bash
pip install pyterametrics
```

## Usage

### Command Line

```bash
# Analyze a single file
pyterametrics --file main.tf -b --target output.json

# Analyze a directory
pyterametrics -l --repo ./terraform-project --target ./results --project my-project

# Pretty-print output
pyterametrics --file main.tf -b --pretty
```

### Python API

```python
from pyterametrics import analyze_file, analyze_directory

# Single file
result = analyze_file("main.tf")
for block in result["blocks"]:
    print(f"{block['block_identifiers']}: {block['numAttrs']} attrs, CC={block['sumMccabeCC']}")

# Directory
result = analyze_directory("./terraform-project", project_name="my-project")
```

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest tests/ -v
```