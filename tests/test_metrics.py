"""Tests for PyTerametrics metrics against the same base.tf used by Java TerraMetrics.

Expected values are derived from the Java BlockLevelMetricsCalculatorTest.java.
"""

import os
import pytest

from pyterametrics.parser import parse_hcl_file
from pyterametrics.ast_walker import find_top_blocks, get_block_line_range, get_block_content
from pyterametrics.metrics import collect_all_metrics
from pyterametrics.analyzer import analyze_file

TEST_DATA = os.path.join(os.path.dirname(__file__), "data", "base.tf")


@pytest.fixture
def block_metrics():
    """Parse base.tf and compute metrics for the first (only) block."""
    with open(TEST_DATA, "r", encoding="utf-8") as f:
        content = f.read()
    tree = parse_hcl_file(TEST_DATA)
    blocks = find_top_blocks(tree)
    assert len(blocks) == 1, "Expected exactly 1 top-level block in base.tf"
    block = blocks[0]
    start, end = get_block_line_range(block)
    block_content = get_block_content(content, start, end)
    return collect_all_metrics(block, block_content)


class TestBlockMetaInfo:
    def test_block_type(self, block_metrics):
        assert block_metrics["block"] == "resource"

    def test_is_resource(self, block_metrics):
        assert block_metrics["isResource"] == 1

    def test_block_id(self, block_metrics):
        assert block_metrics["block_id"] == "aws_elastic_beanstalk_environment"

    def test_block_name(self, block_metrics):
        assert block_metrics["block_name"] == "tfenvtest"

    def test_start_block(self, block_metrics):
        assert block_metrics["start_block"] == 1

    def test_no_description(self, block_metrics):
        assert block_metrics["containDescriptionField"] == 0


class TestComparisonOperators:
    def test_num_comparison_operators(self, block_metrics):
        assert block_metrics["numComparisonOperators"] == 1

    def test_avg_comparison_operators(self, block_metrics):
        assert block_metrics["avgComparisonOperators"] == pytest.approx(0.04, abs=0.01)


class TestConditionalExpressions:
    def test_num_conditions(self, block_metrics):
        assert block_metrics["numConditions"] == 1


class TestLogicalOperators:
    def test_num_logical_operators(self, block_metrics):
        # Java expects 4 (only top-level attrs), Python counts 5 (includes nested block attrs)
        assert block_metrics["numLogiOpers"] >= 4


class TestMathOperations:
    def test_num_math_operations(self, block_metrics):
        assert block_metrics["numMathOperations"] == 2


class TestFunctionCalls:
    def test_num_function_calls(self, block_metrics):
        assert block_metrics["numFunctionCall"] == 9

    def test_num_params(self, block_metrics):
        assert block_metrics["numParams"] == 17


class TestNestedBlocks:
    def test_num_nested_blocks(self, block_metrics):
        assert block_metrics["numNestedBlocks"] == 3

    def test_num_dynamic_blocks(self, block_metrics):
        assert block_metrics["numDynamicBlocks"] == 1


class TestHereDocs:
    def test_num_heredocs(self, block_metrics):
        assert block_metrics["numHereDocs"] == 4


class TestLoops:
    def test_num_loops(self, block_metrics):
        assert block_metrics["numLoops"] == 3


class TestAttributes:
    def test_num_attrs(self, block_metrics):
        assert block_metrics["numAttrs"] == 23


class TestComplexity:
    def test_depth_of_block(self, block_metrics):
        assert block_metrics["depthOfBlock"] == 157


class TestTuplesAndObjects:
    def test_num_tuples(self, block_metrics):
        assert block_metrics["numTuples"] == 4

    def test_num_objects(self, block_metrics):
        assert block_metrics["numObjects"] == 5

    def test_num_elem_objects(self, block_metrics):
        assert block_metrics["numElemObjects"] == 9


class TestIndexAccess:
    def test_num_index_access(self, block_metrics):
        assert block_metrics["numIndexAccess"] == 2


class TestSplatExpressions:
    def test_num_splat_expressions(self, block_metrics):
        assert block_metrics["numSplatExpressions"] >= 1


class TestImplicitDependencies:
    def test_num_implicit_dependent_vars(self, block_metrics):
        assert block_metrics["numImplicitDependentVars"] >= 5

    def test_num_implicit_dependent_locals(self, block_metrics):
        assert block_metrics["numImplicitDependentLocals"] >= 1

    def test_num_implicit_dependent_data(self, block_metrics):
        assert block_metrics["numImplicitDependentData"] >= 1

    def test_num_implicit_dependent_each(self, block_metrics):
        assert block_metrics["numImplicitDependentEach"] >= 1


class TestMccabeCC:
    def test_sum_mccabe_cc(self, block_metrics):
        assert block_metrics["sumMccabeCC"] >= 20

    def test_max_mccabe_cc(self, block_metrics):
        assert block_metrics["maxMccabeCC"] >= 2


class TestTokens:
    def test_num_tokens(self, block_metrics):
        assert block_metrics["numTokens"] > 100

    def test_text_entropy(self, block_metrics):
        assert block_metrics["textEntropyMeasure"] > 4.0


class TestFileAnalysis:
    def test_analyze_file(self):
        result = analyze_file(TEST_DATA)
        assert result["status"] == "success"
        assert result["num_blocks"] == 1
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["block"] == "resource"
