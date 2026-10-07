"""
Function Source Code Parser

This module provides functionality to parse Python function source code using AST,
extracting function signature, docstring, and implementation code separately.
"""

import ast
import inspect
import textwrap
from typing import Any

import black
from pydantic import BaseModel, Field


class FunctionParts(BaseModel):
    """Parsed parts of a function."""

    signature: str = Field(
        description="Function signature string (e.g., 'def func(x: int) -> str:')"
    )
    docstring: str | None = Field(
        default=None, description="Function docstring, or None if not present"
    )
    body_code: list[str] = Field(
        default_factory=list,
        description="Function body code lines (excluding signature and docstring)",
    )
    decorators: list[str] = Field(
        default_factory=list,
        description="Function decorators (e.g., ['@tool(readonly=True)'])",
    )
    is_async: bool = Field(description="Whether the function is async")
    original_name: str = Field(description="Original function name")


class FunctionParser:
    """
    Parse Python function source code using AST to extract different parts.

    This parser uses Python's AST module to accurately parse function definitions,
    extracting:
    - Function signature (with proper formatting)
    - Docstring
    - Body code (implementation)
    - Decorators
    """

    def __init__(self):
        """Initialize the parser."""

    def parse_function(self, func: Any) -> FunctionParts | None:
        """
        Parse a function and extract its parts.

        :param func: The function to parse (can be original or wrapped function)

        :returns: FunctionParts object containing parsed parts, or None if parsing fails
        """
        # Get function source code
        # For bound methods, we need to get the unbound function
        if inspect.ismethod(func):
            func = func.__func__

        # Try to get source code
        source_code = inspect.getsource(func)
        # Add class wrapper
        source_code = textwrap.indent(textwrap.dedent(source_code), "    ")
        source_code = f"class ClassWrapper:\n{source_code}"
        # black format
        source_code = black.format_str(source_code, mode=black.Mode())
        # parse source code
        return self.parse_source(source_code, func.__name__)

    def parse_source(
        self, source_code: str, function_name: str | None = None
    ) -> FunctionParts | None:
        """
        Parse function source code string and extract parts.

        :param source_code: The source code string of the function
        :param function_name: Optional function name (for validation)

        :returns: FunctionParts object containing parsed parts, or None if parsing fails
        """
        try:
            # Parse the source code into AST
            tree = ast.parse(source_code)

            # Find the function definition
            func_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # If function_name is provided, match it
                    if function_name is None or node.name == function_name:
                        func_node = node
                        break

            if func_node is None:
                return None

            # Extract parts
            decorators = self._extract_decorators(func_node, source_code)
            signature = self._extract_signature(func_node, source_code)
            docstring = self._extract_docstring(func_node)
            body_code = self._extract_body_code(func_node, source_code)
            is_async = isinstance(func_node, ast.AsyncFunctionDef)
            original_name = func_node.name

            return FunctionParts(
                signature=signature,
                docstring=docstring,
                body_code=body_code,
                decorators=decorators,
                is_async=is_async,
                original_name=original_name,
            )
        except (SyntaxError, ValueError):
            return None

    def _extract_decorators(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, source_code: str
    ) -> list[str]:
        """
        Extract decorators from function node.

        :param func_node: The function AST node
        :param source_code: Original source code

        :returns: List of decorator strings
        """
        decorators = []
        if not func_node.decorator_list:
            return decorators

        # Get line numbers for decorators
        lines = source_code.split("\n")

        for decorator in func_node.decorator_list:
            # Get the line number of the decorator
            if hasattr(decorator, "lineno"):
                lineno = decorator.lineno - 1  # AST line numbers are 1-based
                if 0 <= lineno < len(lines):
                    decorator_line = lines[lineno].strip()
                    decorators.append(decorator_line)

        return decorators

    def _extract_signature(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, source_code: str
    ) -> str:
        """
        Extract function signature from AST node.

        :param func_node: The function AST node
        :param source_code: Original source code

        :returns: Function signature string
        """
        lines = source_code.split("\n")

        # Get the function definition line(s)
        func_start_line = func_node.lineno - 1  # AST line numbers are 1-based

        # Collect signature lines until we find the colon
        signature_lines = []
        paren_count = 0

        for i in range(func_start_line, len(lines)):
            line = lines[i]
            # Count parentheses to track when signature ends
            paren_count += line.count("(") - line.count(")")
            signature_lines.append(line.strip())

            # Check if this line ends the signature (has colon and parentheses are balanced)
            if ":" in line and paren_count == 0:
                break

        # Join and clean up signature
        signature = " ".join(signature_lines).strip()

        # Ensure it ends with colon
        if not signature.rstrip().endswith(":"):
            signature += ":"

        return signature

    def _extract_docstring(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str | None:
        """
        Extract docstring from function node.

        :param func_node: The function AST node

        :returns: Docstring string, or None if not present
        """
        if (
            func_node.body
            and isinstance(func_node.body[0], ast.Expr)
            and isinstance(func_node.body[0].value, ast.Constant)
            and isinstance(func_node.body[0].value.value, str)
        ):
            return func_node.body[0].value.value

        # Fallback for older Python versions or different AST structures
        if (
            func_node.body
            and isinstance(func_node.body[0], ast.Expr)
            and isinstance(func_node.body[0].value, ast.Str)
        ):
            return func_node.body[0].value.s

        return None

    def _extract_body_code(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, source_code: str
    ) -> list[str]:
        """
        Extract function body code (excluding signature and docstring).

        :param func_node: The function AST node
        :param source_code: Original source code

        :returns: List of body code lines
        """
        lines = source_code.split("\n")

        # Find where the body starts (after signature and docstring)
        body_start_idx = None

        # Skip docstring if present
        if (
            func_node.body
            and isinstance(func_node.body[0], ast.Expr)
            and (
                (
                    isinstance(func_node.body[0].value, ast.Constant)
                    and isinstance(func_node.body[0].value.value, str)
                )
                or isinstance(func_node.body[0].value, ast.Str)
            )
        ):
            # Docstring is the first statement
            docstring_node = func_node.body[0]
            if hasattr(docstring_node, "end_lineno"):
                body_start_idx = docstring_node.end_lineno  # After docstring
            else:
                # Fallback: find the line after docstring
                docstring_line = docstring_node.lineno - 1
                body_start_idx = docstring_line + 1

        # If no docstring, body starts after signature
        if body_start_idx is None:
            # Find the line after function signature
            if hasattr(func_node, "end_lineno") and func_node.end_lineno is not None:
                func_end_line = func_node.end_lineno - 1
            else:
                func_end_line = func_node.lineno - 1
            # Find the line with colon (end of signature)
            for i in range(func_node.lineno - 1, min(func_end_line + 1, len(lines))):
                if ":" in lines[i]:
                    body_start_idx = i + 1
                    break

        if body_start_idx is None:
            return []

        body_end_idx = getattr(func_node, "end_lineno", None) or len(lines)

        # Extract body lines and normalize them relative to the function body.
        # The parser often receives methods wrapped in a synthetic class, so raw
        # source lines include class+method indentation. Formatters add their own
        # indentation later and require body_code to be relative.
        body_lines = []
        for i in range(body_start_idx, min(body_end_idx, len(lines))):
            body_lines.append(lines[i])

        if not body_lines:
            return []

        return textwrap.dedent("\n".join(body_lines)).split("\n")

    def _extract_method_from_class_source(
        self, class_source: str, method_name: str
    ) -> FunctionParts | None:
        """
        Extract a method from class source code.

        :param class_source: The source code of the class
        :param method_name: The name of the method to extract

        :returns: FunctionParts object, or None if not found
        """
        try:
            tree = ast.parse(class_source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if (
                            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == method_name
                        ):
                            # Found the method, extract its source code
                            lines = class_source.split("\n")
                            # Get method source lines
                            method_start = item.lineno - 1
                            method_end = (
                                item.end_lineno
                                if hasattr(item, "end_lineno")
                                else len(lines)
                            )

                            # Extract method source (need to dedent)
                            method_lines = lines[method_start:method_end]
                            if method_lines:
                                # Get base indentation from first line
                                base_indent = len(method_lines[0]) - len(
                                    method_lines[0].lstrip()
                                )
                                # Dedent all lines
                                dedented_lines = [
                                    (
                                        line[base_indent:]
                                        if len(line) > base_indent
                                        else line.lstrip()
                                    )
                                    for line in method_lines
                                ]
                                method_source = "\n".join(dedented_lines)
                                return self.parse_source(method_source, method_name)
            return None
        except Exception:
            return None
