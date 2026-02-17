"""Command-line interface for PyTerametrics.

Matches the CLI arguments of the Java TerraMetrics tool.
"""

import json
import sys

import click

from pyterametrics.analyzer import analyze_file, analyze_directory


@click.command()
@click.option("--file", "-f", "filepath", help="Path to a single .tf file to analyze.")
@click.option("-b", "block_mode", is_flag=True, help="Analyze at the block level (required with --file).")
@click.option("-l", "dir_mode", is_flag=True, help="Analyze a local directory.")
@click.option("--repo", "-r", "repo", help="Path to a local directory of Terraform files.")
@click.option("--target", "-t", "target", help="Output path for results (file or directory).")
@click.option("--project", "-p", "project_name", default="", help="Project name for directory analysis.")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
@click.version_option(package_name="pyterametrics")
def main(filepath, block_mode, dir_mode, repo, target, project_name, pretty):
    """PyTerametrics - IaC quality metrics for Terraform HCL files.

    Analyze Terraform files to compute 100 quality metrics at the block level.

    Examples:

      pyterametrics --file main.tf -b --target output.json

      pyterametrics -l --repo ./terraform-project --target ./results --project my-project
    """
    indent = 2 if pretty else None

    if filepath and block_mode:
        result = analyze_file(filepath, target)
        if not target:
            click.echo(json.dumps(result, indent=indent, ensure_ascii=False))

    elif dir_mode and repo:
        result = analyze_directory(repo, project_name, target)
        if not target:
            click.echo(json.dumps(result, indent=indent, ensure_ascii=False))

    else:
        click.echo("Error: Use --file with -b, or -l with --repo.", err=True)
        click.echo("Run 'pyterametrics --help' for usage.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
