"""AST walking utilities for Lark parse trees.

Replaces Java's ExpressionAnalyzer, TopBlockFinder, AttrFinderImpl,
NestedBlockVisitor, BlockLabelVisitor, and BodyTreeFinder.
"""

from lark import Tree, Token
from typing import List, Optional


def get_all_nodes(tree) -> List:
    """Recursively collect all nodes (Tree and Token) from a parse tree.

    Equivalent to Java's ExpressionAnalyzer.getAllNestedExpressions().
    """
    nodes = []
    if tree is not None:
        nodes.append(tree)
        if isinstance(tree, Tree):
            for child in tree.children:
                nodes.extend(get_all_nodes(child))
    return nodes


def find_nodes_by_rule(tree, rule_name: str) -> List[Tree]:
    """Find all Tree nodes with the given rule name."""
    return [n for n in get_all_nodes(tree) if isinstance(n, Tree) and n.data == rule_name]


def find_tokens(tree) -> List[Token]:
    """Find all Token nodes in the tree."""
    return [n for n in get_all_nodes(tree) if isinstance(n, Token)]


def find_top_blocks(tree: Tree) -> List[Tree]:
    """Extract top-level block nodes from the parsed HCL tree.

    Equivalent to Java's TopBlockFinder.findTopBlock().
    """
    blocks = []
    # The tree root is 'start' -> 'body' -> children
    for child in tree.children:
        if isinstance(child, Tree):
            if child.data == "block":
                blocks.append(child)
            else:
                # Recurse into body/start nodes
                for c2 in child.children:
                    if isinstance(c2, Tree) and c2.data == "block":
                        blocks.append(c2)
    return blocks


def find_attributes(block: Tree) -> List[Tree]:
    """Find all attribute nodes within a block (including nested blocks).

    Equivalent to Java's AttrFinderImpl.getAllAttributes().
    """
    attrs = []
    nested = find_all_nested_blocks(block)
    for b in nested:
        attrs.extend(_get_direct_attributes(b))
    return attrs


def _get_direct_attributes(block: Tree) -> List[Tree]:
    """Get direct attribute children of a block's body.

    Equivalent to Java's AttrFinderImpl.getAttributes().
    """
    attrs = []
    for child in block.children:
        if isinstance(child, Tree):
            if child.data == "attribute":
                attrs.append(child)
            elif child.data == "body":
                for c2 in child.children:
                    if isinstance(c2, Tree) and c2.data == "attribute":
                        attrs.append(c2)
    return attrs


def find_all_nested_blocks(tree) -> List[Tree]:
    """Recursively find all block nodes (including the root block).

    Equivalent to Java's NestedBlockVisitor.getAllNestedBlocks().
    """
    blocks = []
    if tree is not None:
        if isinstance(tree, Tree) and tree.data == "block":
            blocks.append(tree)
        if isinstance(tree, Tree):
            for child in tree.children:
                blocks.extend(find_all_nested_blocks(child))
    return blocks


def get_block_type(block: Tree) -> str:
    """Get the block type keyword (e.g., 'resource', 'data', 'variable').

    Equivalent to Java's identifiedBlock.key().value().
    """
    for child in block.children:
        if isinstance(child, Token) and child.type == "NAME":
            return str(child)
        if isinstance(child, Tree) and child.data == "identifier":
            for t in child.children:
                if isinstance(t, Token):
                    return str(t)
    return ""


def get_block_labels(block: Tree) -> List[str]:
    """Get the labels of a block (e.g., type name and resource name).

    Equivalent to Java's BlockLabelVisitor.identifyLabelsOfBlock().
    """
    labels = []
    for child in block.children:
        if isinstance(child, Token):
            if child.type == "NAME":
                continue  # skip the block type keyword
            labels.append(str(child).strip('"'))
        elif isinstance(child, Tree) and child.data == "identifier":
            # skip the first identifier (block type)
            pass
        elif isinstance(child, Tree) and child.data == "string":
            # String labels (quoted)
            text = _extract_string_value(child)
            labels.append(text)
    return labels


def get_attribute_name(attr: Tree) -> str:
    """Get the name/key of an attribute node."""
    for child in attr.children:
        if isinstance(child, Token) and child.type == "NAME":
            return str(child)
        if isinstance(child, Tree) and child.data == "identifier":
            for t in child.children:
                if isinstance(t, Token):
                    return str(t)
    return ""


def get_attribute_value(attr: Tree) -> Optional[Tree]:
    """Get the value expression of an attribute node."""
    children = [c for c in attr.children if isinstance(c, Tree)]
    # The attribute structure is: identifier "=" expr_term
    # or: NAME "=" expr_term
    # The value is typically the last Tree child
    for child in attr.children:
        if isinstance(child, Tree) and child.data not in ("identifier", "new_line_or_comment", "new_line_and_or_comment"):
            return child
    return None


def get_block_line_range(block: Tree) -> tuple:
    """Get the start and end line numbers of a block.

    Returns (start_line, end_line) tuple.
    """
    start = None
    end = None
    for node in get_all_nodes(block):
        if isinstance(node, Token) and node.line is not None:
            if start is None or node.line < start:
                start = node.line
            if end is None or node.end_line is not None and node.end_line > (end or 0):
                end = node.end_line
            elif node.line > (end or 0):
                end = node.line
    return (start or 1, end or 1)


def _extract_string_value(string_tree: Tree) -> str:
    """Extract the string value from a string tree node."""
    parts = []
    for child in string_tree.children:
        if isinstance(child, Token):
            parts.append(str(child))
        elif isinstance(child, Tree) and child.data == "string_part":
            for t in child.children:
                parts.append(str(t))
    return "".join(parts)


def get_block_content(file_content: str, start_line: int, end_line: int) -> str:
    """Extract block content from file content by line range.

    Equivalent to Java's ServiceCounter.extractDesiredContent().
    """
    lines = file_content.split("\n")
    # 1-indexed
    selected = lines[start_line - 1:end_line]
    return "\n".join(selected) + "\n"
