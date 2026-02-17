"""Metric collectors for HCL blocks.

Each function adds metrics to a dict, following the same pattern and metric names
as the Java TerraMetrics implementation. All 100 metrics from the Java version
are computed here.
"""

import math
import re
from typing import Dict, List, Any, Optional

from lark import Tree, Token

from pyterametrics.ast_walker import (
    get_all_nodes,
    find_nodes_by_rule,
    find_tokens,
    find_attributes,
    find_all_nested_blocks,
    get_block_type,
    get_block_labels,
    get_attribute_name,
    get_attribute_value,
    get_block_line_range,
    _get_direct_attributes,
)


def _round2(value: float) -> float:
    """Round to 2 decimal places using HALF_UP rounding (matching Java BigDecimal)."""
    return round(value + 1e-9, 2)


# =============================================================================
# Provider prefixes for implicit dependency detection
# =============================================================================
PROVIDER_PREFIXES = [
    "aws", "google", "azurerm", "kubernetes", "oci", "alicloud", "google-beta",
    "archive", "helm", "null", "nomad", "random", "template", "tls", "http",
    "time", "waypoint", "vsphere", "vault", "tfe", "terraform", "salesforce",
    "oraclepaas", "opc", "hcs", "hcp", "googleworkspace", "external", "dns",
    "consul", "cloudinit", "boundary", "azurestack", "azuread", "awscc", "ad",
    "kubectl",
]

# Deprecated Terraform functions
DEPRECATED_FUNCTIONS = ["list", "map"]

# Debugging functions
DEBUGGING_FUNCTIONS = ["file", "templatefile"]

# Comparison operators
COMPARISON_OPERATORS = ["==", "!=", "<", ">", "<=", ">="]

# Logical operators
LOGICAL_OPERATORS = ["&&", "||", "!"]

# Math operators
MATH_OPERATORS = ["+", "-", "*", "/", "%"]

# Meta-argument names
META_ARGUMENTS = ["depends_on", "count", "for_each", "provider", "lifecycle"]


# =============================================================================
# Helper: per-attribute counting pattern
# =============================================================================

def _per_attr_stats(block: Tree, count_fn) -> tuple:
    """Count items per attribute and return (total, avg, max).

    Args:
        block: The block tree node.
        count_fn: Function(attribute_tree) -> int, counts items in one attribute.

    Returns:
        (total, avg_rounded, max_val)
    """
    attrs = find_attributes(block)
    if not attrs:
        return (0, 0.0, 0)

    counts = [count_fn(attr) for attr in attrs]
    total = sum(counts)
    avg = _round2(total / len(attrs))
    max_val = max(counts)
    return (total, avg, max_val)


def _count_in_expr(attr: Tree, rule_name: str) -> int:
    """Count tree nodes of a given rule type within an attribute's value expression."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    return len(find_nodes_by_rule(val, rule_name))


# =============================================================================
# Individual metric collectors
# =============================================================================

def collect_block_meta_info(metrics: Dict, block: Tree) -> None:
    """Block meta information: type, labels, line range."""
    block_type = get_block_type(block)
    labels = get_block_labels(block)
    start_line, end_line = get_block_line_range(block)

    metrics["impacted_block_type"] = " ".join(labels)
    metrics["block"] = block_type
    metrics["start_block"] = start_line
    metrics["end_block"] = end_line

    full_labels = [block_type] + labels
    metrics["block_identifiers"] = " ".join(full_labels)

    if len(full_labels) == 3:
        metrics["block_id"] = full_labels[1]
        metrics["block_name"] = full_labels[2]
    elif len(full_labels) == 2:
        metrics["block_id"] = ""
        metrics["block_name"] = full_labels[1]
    else:
        metrics["block_id"] = ""
        metrics["block_name"] = ""


def collect_block_type(metrics: Dict, block: Tree) -> None:
    """Check the block type (resource, module, data, etc.)."""
    block_type = get_block_type(block)
    metrics["isResource"] = 1 if block_type == "resource" else 0
    metrics["isModule"] = 1 if block_type == "module" else 0
    metrics["isData"] = 1 if block_type == "data" else 0
    metrics["isTerraform"] = 1 if block_type == "terraform" else 0
    metrics["isProvider"] = 1 if block_type == "provider" else 0
    metrics["isVariable"] = 1 if block_type == "variable" else 0
    metrics["isOutput"] = 1 if block_type == "output" else 0
    metrics["isLocals"] = 1 if block_type == "locals" else 0

    # Check if block contains a 'description' field
    attrs = _get_direct_attributes(block)
    has_desc = any(get_attribute_name(a) == "description" for a in attrs)
    # Also check nested blocks
    if not has_desc:
        for nested in find_all_nested_blocks(block):
            dattrs = _get_direct_attributes(nested)
            if any(get_attribute_name(a) == "description" for a in dattrs):
                has_desc = True
                break
    metrics["containDescriptionField"] = 1 if has_desc else 0


def collect_block_complexity(metrics: Dict, block: Tree, block_content: str) -> None:
    """Block complexity: depth, LOC, NLOC."""
    start_line, end_line = get_block_line_range(block)
    depth = end_line - start_line + 1
    metrics["depthOfBlock"] = depth

    # Count lines of code (non-blank, non-comment lines)
    loc = _count_loc(block_content)
    metrics["loc"] = max(loc, 0)

    # Count non-code lines (blank + comment)
    nloc = _count_nloc(block_content)
    metrics["nloc"] = max(nloc, 0)


def _count_loc(content: str) -> int:
    """Count lines of code (excluding comments and blank lines)."""
    # Remove multi-line comments
    cleaned = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove single-line # comments
    cleaned = re.sub(r'#[^\n]*', '', cleaned)
    # Remove single-line // comments
    cleaned = re.sub(r'//[^\n]*', '', cleaned)

    count = 0
    for line in cleaned.split("\n"):
        if line.strip():
            count += 1
    return count


def _count_nloc(content: str) -> int:
    """Count non-code lines (blank lines + comment lines)."""
    blank = sum(1 for line in content.split("\n") if not line.strip())
    comments = _count_comment_lines(content)
    return blank + comments


def _count_comment_lines(content: str) -> int:
    """Count comment lines (single-line # and multi-line /* */)."""
    count = 0
    # Multi-line comments
    for match in re.finditer(r'/\*.*?\*/', content, flags=re.DOTALL):
        comment_text = match.group()
        for line in comment_text.split("\n"):
            if line.strip():
                count += 1
    # Single-line # comments
    count += len(re.findall(r'#[^\n]*', content))
    return count


def collect_attributes(metrics: Dict, block: Tree) -> None:
    """Count total attributes."""
    attrs = find_attributes(block)
    metrics["numAttrs"] = len(attrs)


def _count_binary_ops_by_operators(attr: Tree, operators: List[str]) -> int:
    """Count binary operations matching specific operators within an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "binary_operator":
            # binary_operator contains a single BINARY_OP token
            for child in node.children:
                if isinstance(child, Token):
                    op_str = str(child).strip()
                    if op_str in operators:
                        count += 1
    return count


def collect_comparison_operators(metrics: Dict, block: Tree) -> None:
    """Comparison operators: num, avg, max."""
    total, avg, mx = _per_attr_stats(
        block,
        lambda attr: _count_binary_ops_by_operators(attr, COMPARISON_OPERATORS),
    )
    metrics["numComparisonOperators"] = total
    metrics["avgComparisonOperators"] = avg
    metrics["maxComparisonOperators"] = mx


def _count_conditionals_in_attr(attr: Tree) -> int:
    """Count conditional expressions in an attribute (ternary ? : and if directives)."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "conditional":
            count += 1
        # Also count 'if' tokens used in for-expressions (%{if ...})
        if isinstance(node, Token) and str(node) == "if" and node.type == "NAME":
            # This is a Terraform for-expression 'if' clause
            count += 1
    return count


def collect_conditionals(metrics: Dict, block: Tree) -> None:
    """Conditional expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_conditionals_in_attr)
    metrics["numConditions"] = total
    metrics["avgConditions"] = avg
    metrics["maxConditions"] = mx


def collect_logical_operators(metrics: Dict, block: Tree) -> None:
    """Logical operators (&&, ||, !): num, avg, max."""
    total, avg, mx = _per_attr_stats(
        block,
        lambda attr: _count_binary_ops_by_operators(attr, LOGICAL_OPERATORS),
    )
    metrics["numLogiOpers"] = total
    metrics["avgLogiOpers"] = avg
    metrics["maxLogiOpers"] = mx


def collect_dynamic_blocks(metrics: Dict, block: Tree) -> None:
    """Count dynamic blocks."""
    count = 0
    for nested in find_all_nested_blocks(block):
        btype = get_block_type(nested)
        if btype == "dynamic":
            count += 1
    metrics["numDynamicBlocks"] = count


def collect_nested_blocks(metrics: Dict, block: Tree) -> None:
    """Nested blocks: count, avg/max/min depth."""
    # Find nested blocks (excluding the root block itself)
    all_nested = find_all_nested_blocks(block)
    # The first one is the root block itself, nested are after it
    nested_only = [b for b in all_nested if b is not block]

    metrics["numNestedBlocks"] = len(nested_only)

    if nested_only:
        depths = []
        for nb in nested_only:
            s, e = get_block_line_range(nb)
            depths.append(e - s + 1)
        metrics["avgDepthNestedBlocks"] = _round2(sum(depths) / len(depths))
        metrics["maxDepthNestedBlocks"] = max(depths)
        metrics["minDepthNestedBlocks"] = min(depths)
    else:
        metrics["avgDepthNestedBlocks"] = 0.0
        metrics["maxDepthNestedBlocks"] = 0
        metrics["minDepthNestedBlocks"] = 0


def _count_function_calls(attr: Tree) -> int:
    """Count function call expressions in an attribute."""
    return _count_in_expr(attr, "function_call")


def collect_function_calls(metrics: Dict, block: Tree) -> None:
    """Function call expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_function_calls)
    metrics["numFunctionCall"] = total
    metrics["avgFunctionCall"] = avg
    metrics["maxFunctionCall"] = mx


def _count_function_params(attr: Tree) -> int:
    """Count total function parameters in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "function_call":
            # Count arguments
            for child in node.children:
                if isinstance(child, Tree) and child.data == "arguments":
                    # arguments contains comma-separated expressions
                    arg_count = sum(
                        1 for c in child.children
                        if isinstance(c, Tree) and c.data not in ("new_line_or_comment", "new_line_and_or_comment")
                    )
                    count += arg_count
    return count


def _get_function_calls_from_attr(attr: Tree) -> List[Tree]:
    """Get all function_call nodes from an attribute's value."""
    val = get_attribute_value(attr)
    if val is None:
        return []
    return find_nodes_by_rule(val, "function_call")


def collect_function_params(metrics: Dict, block: Tree) -> None:
    """Function parameters: num, avg per function call, max per function call."""
    attrs = find_attributes(block)
    all_fcs = []
    for attr in attrs:
        all_fcs.extend(_get_function_calls_from_attr(attr))

    if not all_fcs:
        metrics["numParams"] = 0
        metrics["avgParams"] = 0.0
        metrics["maxParams"] = 0
        return

    total_params = 0
    max_params = 0
    for fc in all_fcs:
        pc = 0
        for child in fc.children:
            if isinstance(child, Tree) and child.data == "arguments":
                pc = sum(
                    1 for c in child.children
                    if isinstance(c, Tree) and c.data not in ("new_line_or_comment", "new_line_and_or_comment")
                )
        total_params += pc
        if pc > max_params:
            max_params = pc
    avg_params = _round2(total_params / len(all_fcs))
    metrics["numParams"] = total_params
    metrics["avgParams"] = avg_params
    metrics["maxParams"] = max_params


def _count_heredocs_in_attr(attr: Tree) -> int:
    """Count heredoc expressions in an attribute."""
    return _count_in_expr(attr, "heredoc_template")


def _count_heredoc_lines(attr: Tree) -> int:
    """Count total lines in heredoc expressions in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    lines = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "heredoc_template":
            # Count newlines inside the heredoc
            tokens = find_tokens(node)
            heredoc_text = "".join(str(t) for t in tokens)
            # Count lines between the opening and closing markers
            heredoc_lines = heredoc_text.count("\n")
            lines += heredoc_lines
    return lines


def collect_heredocs(metrics: Dict, block: Tree) -> None:
    """HereDocs: num, avg, lines count, avg lines, max lines."""
    attrs = find_attributes(block)
    total_heredocs = 0
    total_lines = 0
    max_lines = 0

    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        heredocs = find_nodes_by_rule(val, "heredoc_template")
        total_heredocs += len(heredocs)

        for hd in heredocs:
            # Count lines in this heredoc
            tokens = find_tokens(hd)
            text = "".join(str(t) for t in tokens)
            # Lines between delimiters (subtract the delimiter lines)
            hd_lines = text.count("\n")
            # Subtract 1 for the opening/closing
            if hd_lines > 0:
                hd_lines -= 1
            total_lines += hd_lines
            if hd_lines > max_lines:
                max_lines = hd_lines

    metrics["numHereDocs"] = total_heredocs
    if attrs:
        metrics["avgHereDocs"] = _round2(total_heredocs / len(attrs))
    else:
        metrics["avgHereDocs"] = 0.0
    metrics["numLinesHereDocs"] = total_lines
    if total_heredocs > 0:
        metrics["avgLinesHereDocs"] = _round2(total_lines / total_heredocs)
    else:
        metrics["avgLinesHereDocs"] = 0.0
    metrics["maxLinesHereDocs"] = max_lines


def collect_index_access(metrics: Dict, block: Tree) -> None:
    """Index access expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(
        block, lambda attr: _count_in_expr(attr, "index")
    )
    metrics["numIndexAccess"] = total
    metrics["avgIndexAccess"] = avg
    metrics["maxIndexAccess"] = mx


def _count_literals(attr: Tree) -> int:
    """Count literal expressions in an attribute (int, bool, string, null)."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "int_lit":
            count += 1
        elif isinstance(node, Token) and node.type in ("TRUE", "FALSE", "NULL"):
            count += 1
        elif isinstance(node, Tree) and node.data == "string":
            count += 1
    return count


def _count_string_values(attr: Tree) -> int:
    """Count string literal values in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    return len(find_nodes_by_rule(val, "string"))


def collect_literals(metrics: Dict, block: Tree) -> None:
    """Literal expressions and string values."""
    attrs = find_attributes(block)
    total_literals = sum(_count_literals(a) for a in attrs)
    total_strings = sum(_count_string_values(a) for a in attrs)
    metrics["numLiteralExpression"] = total_literals
    metrics["numStringValues"] = total_strings


def _count_loops(attr: Tree) -> int:
    """Count loop expressions (for expressions) in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    count += len(find_nodes_by_rule(val, "for_tuple_expr"))
    count += len(find_nodes_by_rule(val, "for_object_expr"))
    return count


def collect_loops(metrics: Dict, block: Tree) -> None:
    """Loop expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_loops)
    metrics["numLoops"] = total
    metrics["avgLoops"] = avg
    metrics["maxLoops"] = mx


def collect_math_operations(metrics: Dict, block: Tree) -> None:
    """Math operations: num, avg, max."""
    total, avg, mx = _per_attr_stats(
        block,
        lambda attr: _count_binary_ops_by_operators(attr, MATH_OPERATORS),
    )
    metrics["numMathOperations"] = total
    metrics["avgMathOperations"] = avg
    metrics["maxMathOperations"] = mx


def _mccabe_cc_for_attr(attr: Tree) -> int:
    """Compute McCabe Cyclomatic Complexity for an attribute.

    CC = conditions + loops + 1 (per attribute).
    """
    conds = _count_conditionals_in_attr(attr)
    loops = _count_loops(attr)
    return conds + loops + 1


def collect_mccabe_cc(metrics: Dict, block: Tree) -> None:
    """McCabe Cyclomatic Complexity: avg, sum, max."""
    attrs = find_attributes(block)
    if not attrs:
        metrics["avgMccabeCC"] = 0.0
        metrics["sumMccabeCC"] = 0
        metrics["maxMccabeCC"] = 0
        return

    ccs = [_mccabe_cc_for_attr(a) for a in attrs]
    metrics["sumMccabeCC"] = sum(ccs)
    metrics["avgMccabeCC"] = _round2(sum(ccs) / len(ccs))
    metrics["maxMccabeCC"] = max(ccs)


def collect_meta_args(metrics: Dict, block: Tree) -> None:
    """Count meta-arguments (depends_on, count, for_each, provider, lifecycle)."""
    attrs = _get_direct_attributes(block)
    count = sum(1 for a in attrs if get_attribute_name(a) in META_ARGUMENTS)
    # Also check for meta-argument blocks like lifecycle
    nested = find_all_nested_blocks(block)
    for nb in nested:
        if nb is block:
            continue
        btype = get_block_type(nb)
        if btype in META_ARGUMENTS:
            count += 1
    metrics["numMetaArg"] = count


def _count_objects(attr: Tree) -> int:
    """Count object expressions in an attribute."""
    return _count_in_expr(attr, "object")


def collect_objects(metrics: Dict, block: Tree) -> None:
    """Object wrappers: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_objects)
    metrics["numObjects"] = total
    metrics["avgObjects"] = avg
    metrics["maxObjects"] = mx


def _count_object_elements(attr: Tree) -> int:
    """Count object elements in an attribute."""
    return _count_in_expr(attr, "object_elem")


def collect_object_elements(metrics: Dict, block: Tree) -> None:
    """Object elements: num, avg per object, max per object."""
    attrs = find_attributes(block)
    all_objects = []
    for attr in attrs:
        val = get_attribute_value(attr)
        if val:
            all_objects.extend(find_nodes_by_rule(val, "object"))

    total_elems = 0
    max_elems = 0
    for obj in all_objects:
        elems = len(find_nodes_by_rule(obj, "object_elem"))
        total_elems += elems
        if elems > max_elems:
            max_elems = elems

    metrics["numElemObjects"] = total_elems
    if all_objects:
        metrics["avgElemObjects"] = _round2(total_elems / len(all_objects))
    else:
        metrics["avgElemObjects"] = 0.0
    metrics["maxElemObjects"] = max_elems


def _count_references(attr: Tree) -> int:
    """Count reference/attribute access expressions in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    return len(find_nodes_by_rule(val, "get_attr"))


def collect_references(metrics: Dict, block: Tree) -> None:
    """References (attribute access / get_attr): num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_references)
    metrics["numReferences"] = total
    metrics["avgReferences"] = avg
    metrics["maxReferences"] = mx


def _count_variables(attr: Tree) -> int:
    """Count variable expressions (identifiers used as values) in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = 0
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "expr_term":
            # Check if this is a simple identifier reference (variable)
            children = [c for c in node.children if isinstance(c, (Tree, Token))]
            if children and isinstance(children[0], Tree) and children[0].data == "identifier":
                count += 1
            elif children and isinstance(children[0], Token) and children[0].type == "NAME":
                count += 1
    return count


def collect_variables(metrics: Dict, block: Tree) -> None:
    """Variable references: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_variables)
    metrics["numVars"] = total
    metrics["avgNumVars"] = avg
    metrics["maxNumVars"] = mx


def _count_splat(attr: Tree) -> int:
    """Count splat expressions in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    count = len(find_nodes_by_rule(val, "attr_splat"))
    count += len(find_nodes_by_rule(val, "full_splat"))
    # Also check for .* patterns
    for node in get_all_nodes(val):
        if isinstance(node, Tree) and node.data == "attr_splat_expr_term":
            count += 1
    return count


def collect_splat_expressions(metrics: Dict, block: Tree) -> None:
    """Splat expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_splat)
    metrics["numSplatExpressions"] = total
    metrics["avgSplatExpressions"] = avg
    metrics["maxSplatExpressions"] = mx


def _count_template_expressions(attr: Tree) -> int:
    """Count template/interpolation expressions in an attribute."""
    val = get_attribute_value(attr)
    if val is None:
        return 0
    return len(find_nodes_by_rule(val, "interpolation"))


def collect_template_expressions(metrics: Dict, block: Tree) -> None:
    """Template expressions (interpolations): num, avg."""
    attrs = find_attributes(block)
    total = sum(_count_template_expressions(a) for a in attrs)
    metrics["numTemplateExpression"] = total
    if attrs:
        metrics["avgTemplateExpression"] = _round2(total / len(attrs))
    else:
        metrics["avgTemplateExpression"] = 0.0


def _text_entropy(text: str) -> float:
    """Compute Shannon text entropy."""
    if not text:
        return 0.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    total = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return _round2(entropy)


def _tokenize(tree) -> List[str]:
    """Extract all non-whitespace token values from a tree."""
    tokens = find_tokens(tree)
    return [str(t) for t in tokens if str(t).strip()]


def _textualize(tree) -> str:
    """Get all non-whitespace characters from tokens for entropy calculation."""
    tokens = find_tokens(tree)
    chars = []
    for t in tokens:
        val = str(t)
        for c in val:
            if not c.isspace():
                chars.append(c)
    return "".join(chars)


def collect_tokens(metrics: Dict, block: Tree) -> None:
    """Token count, text entropy, and per-attribute token/entropy stats."""
    # Block-level text entropy
    block_text = _textualize(block)
    metrics["textEntropyMeasure"] = _text_entropy(block_text)

    # Per-attribute token count and entropy
    attrs = find_attributes(block)
    all_tokens = _tokenize(block)
    metrics["numTokens"] = len(all_tokens)

    if attrs:
        attr_token_counts = []
        attr_entropies = []
        for attr in attrs:
            tokens = _tokenize(attr)
            attr_token_counts.append(len(tokens))
            text = _textualize(attr)
            attr_entropies.append(_text_entropy(text))

        metrics["minTokensPerAttr"] = min(attr_token_counts)
        metrics["maxTokensPerAttr"] = max(attr_token_counts)
        metrics["avgTokensPerAttr"] = _round2(sum(attr_token_counts) / len(attrs))
        metrics["minAttrsTextEntropy"] = min(attr_entropies)
        metrics["maxAttrsTextEntropy"] = max(attr_entropies)
        metrics["avgAttrsTextEntropy"] = _round2(sum(attr_entropies) / len(attrs))
    else:
        metrics["minTokensPerAttr"] = 0
        metrics["maxTokensPerAttr"] = 0
        metrics["avgTokensPerAttr"] = 0.0
        metrics["minAttrsTextEntropy"] = 0.0
        metrics["maxAttrsTextEntropy"] = 0.0
        metrics["avgAttrsTextEntropy"] = 0.0


def _count_tuples(attr: Tree) -> int:
    """Count tuple expressions in an attribute."""
    return _count_in_expr(attr, "tuple")


def collect_tuples(metrics: Dict, block: Tree) -> None:
    """Tuple expressions: num, avg, max."""
    total, avg, mx = _per_attr_stats(block, _count_tuples)
    metrics["numTuples"] = total
    metrics["avgTuples"] = avg
    metrics["maxTuples"] = mx


def collect_tuple_elements(metrics: Dict, block: Tree) -> None:
    """Tuple elements: total, avg per tuple, max per tuple."""
    attrs = find_attributes(block)
    all_tuples = []
    for attr in attrs:
        val = get_attribute_value(attr)
        if val:
            all_tuples.extend(find_nodes_by_rule(val, "tuple"))

    total_elems = 0
    max_elems = 0
    for tup in all_tuples:
        # Count direct expression children (elements)
        elems = sum(
            1 for c in tup.children
            if isinstance(c, Tree) and c.data not in ("new_line_or_comment", "new_line_and_or_comment")
        )
        total_elems += elems
        if elems > max_elems:
            max_elems = elems

    metrics["numElemTuples"] = total_elems
    if all_tuples:
        metrics["avgElemTuples"] = _round2(total_elems / len(all_tuples))
    else:
        metrics["avgElemTuples"] = 0.0
    metrics["maxElemTuples"] = max_elems


def collect_explicit_deps(metrics: Dict, block: Tree) -> None:
    """Count explicit resource dependencies (depends_on)."""
    attrs = _get_direct_attributes(block)
    count = 0
    for attr in attrs:
        if get_attribute_name(attr) == "depends_on":
            val = get_attribute_value(attr)
            if val:
                # Count elements in the depends_on list
                tuples = find_nodes_by_rule(val, "tuple")
                for tup in tuples:
                    count += sum(
                        1 for c in tup.children
                        if isinstance(c, Tree)
                        and c.data not in ("new_line_or_comment", "new_line_and_or_comment")
                    )
    metrics["numExplicitResourceDependency"] = count


def _get_all_variable_names(block: Tree) -> List[str]:
    """Get all variable/identifier names used as expression roots in the block."""
    attrs = find_attributes(block)
    names = []
    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        for node in get_all_nodes(val):
            if isinstance(node, Tree) and node.data == "expr_term":
                children = [c for c in node.children if isinstance(c, (Tree, Token))]
                if children:
                    first = children[0]
                    if isinstance(first, Tree) and first.data == "identifier":
                        for t in first.children:
                            if isinstance(t, Token):
                                names.append(str(t))
                    elif isinstance(first, Token) and first.type == "NAME":
                        names.append(str(first))
    return names


def collect_implicit_deps(metrics: Dict, block: Tree) -> None:
    """Implicit resource dependencies based on variable name prefixes."""
    names = _get_all_variable_names(block)

    metrics["numImplicitDependentVars"] = sum(1 for n in names if n == "var")
    metrics["numImplicitDependentLocals"] = sum(1 for n in names if n == "local")
    metrics["numImplicitDependentModules"] = sum(1 for n in names if n == "module")
    metrics["numImplicitDependentData"] = sum(1 for n in names if n == "data")
    metrics["numImplicitDependentProviders"] = sum(
        1 for n in names if n == "provider" or n in PROVIDER_PREFIXES
    )
    metrics["numImplicitDependentResources"] = sum(
        1 for n in names
        if any(n.startswith(prefix + "_") for prefix in PROVIDER_PREFIXES)
    )
    metrics["numImplicitDependentEach"] = sum(1 for n in names if n == "each")


def _get_all_string_values(block: Tree) -> List[str]:
    """Get all string literal values from the block."""
    attrs = find_attributes(block)
    strings = []
    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        for node in get_all_nodes(val):
            if isinstance(node, Tree) and node.data == "string":
                text = ""
                for child in node.children:
                    if isinstance(child, Token):
                        text += str(child)
                    elif isinstance(child, Tree):
                        for t in find_tokens(child):
                            text += str(t)
                strings.append(text)
    return strings


def collect_special_strings(metrics: Dict, block: Tree) -> None:
    """Special string patterns: empty strings, wildcard suffix, star strings."""
    strings = _get_all_string_values(block)

    metrics["numEmptyString"] = sum(1 for s in strings if s == "")
    metrics["numWildCardSuffixString"] = sum(1 for s in strings if ":*" in s)
    metrics["numStarString"] = sum(1 for s in strings if s == "*" or "*" in s)


def collect_deprecated_functions(metrics: Dict, block: Tree) -> None:
    """Count deprecated function calls (list, map)."""
    attrs = find_attributes(block)
    count = 0
    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        for node in get_all_nodes(val):
            if isinstance(node, Tree) and node.data == "function_call":
                # Get function name
                for child in node.children:
                    if isinstance(child, Tree) and child.data == "identifier":
                        for t in child.children:
                            if isinstance(t, Token) and str(t) in DEPRECATED_FUNCTIONS:
                                count += 1
                    elif isinstance(child, Token) and child.type == "NAME" and str(child) in DEPRECATED_FUNCTIONS:
                        count += 1
    metrics["numDeprecatedFunctions"] = count


def collect_debugging_functions(metrics: Dict, block: Tree) -> None:
    """Count debugging function calls (file, templatefile)."""
    attrs = find_attributes(block)
    count = 0
    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        for node in get_all_nodes(val):
            if isinstance(node, Tree) and node.data == "function_call":
                for child in node.children:
                    if isinstance(child, Tree) and child.data == "identifier":
                        for t in child.children:
                            if isinstance(t, Token) and str(t) in DEBUGGING_FUNCTIONS:
                                count += 1
                    elif isinstance(child, Token) and child.type == "NAME" and str(child) in DEBUGGING_FUNCTIONS:
                        count += 1
    metrics["numDebuggingFunctions"] = count


def collect_lookup_functions(metrics: Dict, block: Tree) -> None:
    """Count lookup function calls."""
    attrs = find_attributes(block)
    count = 0
    for attr in attrs:
        val = get_attribute_value(attr)
        if val is None:
            continue
        for node in get_all_nodes(val):
            if isinstance(node, Tree) and node.data == "function_call":
                for child in node.children:
                    if isinstance(child, Tree) and child.data == "identifier":
                        for t in child.children:
                            if isinstance(t, Token) and str(t) == "lookup":
                                count += 1
                    elif isinstance(child, Token) and child.type == "NAME" and str(child) == "lookup":
                        count += 1
    metrics["numLookUpFunctionCall"] = count


# =============================================================================
# Main entry point
# =============================================================================

def collect_all_metrics(block: Tree, block_content: str = "") -> Dict[str, Any]:
    """Compute all metrics for a single HCL block.

    This is the main entry point equivalent to Java's
    BlockLevelMetricsCalculator.measureMetrics().

    Args:
        block: Lark Tree node representing the HCL block.
        block_content: The raw text content of the block (for LOC/NLOC counting).

    Returns:
        Dictionary with all metric values.
    """
    metrics: Dict[str, Any] = {}

    collect_block_meta_info(metrics, block)
    collect_block_type(metrics, block)
    collect_block_complexity(metrics, block, block_content)
    collect_attributes(metrics, block)
    collect_comparison_operators(metrics, block)
    collect_conditionals(metrics, block)
    collect_logical_operators(metrics, block)
    collect_dynamic_blocks(metrics, block)
    collect_nested_blocks(metrics, block)
    collect_function_calls(metrics, block)
    collect_function_params(metrics, block)
    collect_heredocs(metrics, block)
    collect_index_access(metrics, block)
    collect_literals(metrics, block)
    collect_loops(metrics, block)
    collect_math_operations(metrics, block)
    collect_mccabe_cc(metrics, block)
    collect_meta_args(metrics, block)
    collect_objects(metrics, block)
    collect_object_elements(metrics, block)
    collect_references(metrics, block)
    collect_variables(metrics, block)
    collect_splat_expressions(metrics, block)
    collect_template_expressions(metrics, block)
    collect_tokens(metrics, block)
    collect_tuples(metrics, block)
    collect_tuple_elements(metrics, block)
    collect_explicit_deps(metrics, block)
    collect_implicit_deps(metrics, block)
    collect_special_strings(metrics, block)
    collect_deprecated_functions(metrics, block)
    collect_debugging_functions(metrics, block)
    collect_lookup_functions(metrics, block)

    return metrics
