"""Python parser using tree-sitter.

Extracts functions, classes, methods, imports, and function calls from Python source.
"""

from __future__ import annotations

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from project_understanding.ingest.parser_base import (
    ParsedCall,
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    compute_symbol_hash,
    extract_docstring,
)


class PythonParser:
    """Tree-sitter based parser for Python source code."""

    def __init__(self) -> None:
        self._language = Language(tspython.language())
        self._parser = Parser(self._language)

    def parse(self, file_path: str, content: str) -> ParsedFile:
        """Parse Python source code and extract symbols, imports, calls."""
        tree = self._parser.parse(content.encode("utf-8"))
        root = tree.root_node

        result = ParsedFile(file_path=file_path, language="python")

        self._walk_node(root, content, result, parent_path="")

        return result

    def _walk_node(
        self,
        node: Node,
        content: str,
        result: ParsedFile,
        parent_path: str = "",
    ) -> None:
        """Recursively walk the tree-sitter AST and extract information."""
        if node.type == "import_statement":
            imp = self._parse_import(node, content)
            if imp:
                result.imports.append(imp)

        elif node.type == "import_from_statement":
            imp = self._parse_from_import(node, content)
            if imp:
                result.imports.append(imp)

        elif node.type == "function_definition":
            symbol = self._parse_function(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "class_definition":
            symbol = self._parse_class(node, content, parent_path, result)
            result.symbols.append(symbol)

        elif node.type == "decorated_definition":
            # Process the inner definition
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    self._walk_node(child, content, result, parent_path)

        elif node.type == "assignment":
            # Check for module-level constants (UPPER_CASE = ...)
            sym = self._try_parse_constant(node, content, parent_path)
            if sym:
                result.symbols.append(sym)

        # Recurse into children for unhandled node types
        if node.type not in ("class_definition",):
            for child in node.children:
                self._walk_node(child, content, result, parent_path)

    def _parse_import(self, node: Node, content: str) -> ParsedImport | None:
        """Parse a simple import statement: import X, Y."""
        if not node.children:
            return None

        names: list[str] = []
        for child in node.children:
            if child.type in ("dotted_name", "aliased_import"):
                text = content[child.start_byte:child.end_byte]
                names.append(text.strip())

        return ParsedImport(
            module_path=", ".join(names) if names else "",
            names=names,
            is_from_import=False,
            line=node.start_point[0] + 1,
        )

    def _parse_from_import(self, node: Node, content: str) -> ParsedImport | None:
        """Parse a from-import statement: from X import Y, Z."""
        module_path = ""
        names: list[str] = []

        for child in node.children:
            if child.type == "dotted_name" and not module_path:
                module_path = content[child.start_byte:child.end_byte]
            elif child.type == "wildcard_import":
                names = ["*"]
            elif child.type == "import_list":
                for item in child.children:
                    if item.type in ("dotted_name", "identifier", "aliased_import"):
                        text = content[item.start_byte:item.end_byte]
                        names.append(text.strip())
                    elif item.type == "wildcard_import":
                        names.append("*")

        return ParsedImport(
            module_path=module_path,
            names=names,
            is_from_import=True,
            line=node.start_point[0] + 1,
        )

    def _parse_function(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol:
        """Parse a function definition."""
        name = ""
        params: list[str] = []
        return_type = ""
        is_async = False
        visibility = "public"
        decorators: list[str] = []

        # Check for async keyword in siblings or parent
        for child in node.children:
            if child.type == "identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "parameters":
                params = self._extract_parameters(child, content)
            elif child.type == "type":
                return_type = content[child.start_byte:child.end_byte]
            elif child.type == "async":
                is_async = True

        # Check if private (starts with _)
        if name.startswith("__") and name.endswith("__"):
            visibility = "special"
        elif name.startswith("_"):
            visibility = "protected"
        elif name.startswith("__"):
            visibility = "private"

        # Check parent for decorators
        if node.parent and node.parent.type == "decorated_definition":
            for sibling in node.parent.children:
                if sibling.type == "decorator":
                    dec_text = content[sibling.start_byte:sibling.end_byte]
                    decorators.append(dec_text)

                    # Detect staticmethod/classmethod
                    if "staticmethod" in dec_text:
                        is_static = True  # noqa: F841
                    if "classmethod" in dec_text:
                        pass  # class method, still a method

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name

        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Extract calls from function body
        calls = self._extract_calls(node, content, name)
        # Calls are added to ParsedFile separately — we return them via symbol for context

        kind = "method" if parent_path else "function"

        return ParsedSymbol(
            name=name,
            kind=kind,
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            is_async=is_async,
            parameters=params,
            return_type=return_type,
            docstring=doc,
        )

    def _parse_class(
        self,
        node: Node,
        content: str,
        parent_path: str,
        result: ParsedFile,
    ) -> ParsedSymbol:
        """Parse a class definition, including methods."""
        name = ""
        bases: list[str] = []
        visibility = "public"

        for child in node.children:
            if child.type == "identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "argument_list":
                # Base classes
                for arg in child.children:
                    if arg.type in ("identifier", "attribute", "dotted_name"):
                        bases.append(content[arg.start_byte:arg.end_byte])

        if name.startswith("_"):
            visibility = "protected"

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Parse class body for methods
        methods: list[ParsedSymbol] = []
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "function_definition":
                        method = self._parse_function(stmt, content, qual_path)
                        methods.append(method)
                    elif stmt.type == "decorated_definition":
                        for dec_child in stmt.children:
                            if dec_child.type == "function_definition":
                                method = self._parse_function(dec_child, content, qual_path)
                                methods.append(method)
                    elif stmt.type == "expression_statement":
                        # Check for class-level assignments (constants)
                        for expr_child in stmt.children:
                            if expr_child.type == "assignment":
                                sym = self._try_parse_constant(
                                    expr_child, content, qual_path
                                )
                                if sym:
                                    methods.append(sym)

        # Extract calls from class body
        calls = self._extract_calls(node, content, name)

        return ParsedSymbol(
            name=name,
            kind="class",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            parameters=[],
            return_type="",
            docstring=doc,
            children=methods,
        )

    def _try_parse_constant(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol | None:
        """Try to parse a module/class-level constant assignment."""
        left = None
        for child in node.children:
            if child.type == "identifier" and left is None:
                left = content[child.start_byte:child.end_byte]

        if left and left.isupper():
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            qual_path = f"{parent_path}.{left}" if parent_path else left
            symbol_hash = compute_symbol_hash(content, line_start, line_end)
            return ParsedSymbol(
                name=left,
                kind="constant",
                path=qual_path,
                line_start=line_start,
                line_end=line_end,
                hash=symbol_hash,
                visibility="public",
            )

        return None

    def _extract_parameters(self, params_node: Node, content: str) -> list[str]:
        """Extract parameter names from a parameter list."""
        params: list[str] = []
        for child in params_node.children:
            if child.type == "identifier":
                params.append(content[child.start_byte:child.end_byte])
            elif child.type == "typed_parameter":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append(content[sub.start_byte:sub.end_byte])
                        break
            elif child.type == "default_parameter":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append(content[sub.start_byte:sub.end_byte])
                        break
            elif child.type == "typed_default_parameter":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append(content[sub.start_byte:sub.end_byte])
                        break
            elif child.type == "list_splat_pattern":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append("*" + content[sub.start_byte:sub.end_byte])
            elif child.type == "dictionary_splat_pattern":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append("**" + content[sub.start_byte:sub.end_byte])
        return params

    def _extract_calls(
        self, node: Node, content: str, context_name: str
    ) -> list[ParsedCall]:
        """Extract function/method calls from a node."""
        calls: list[ParsedCall] = []
        self._collect_calls(node, content, context_name, calls)
        return calls

    def _collect_calls(
        self,
        node: Node,
        content: str,
        context_name: str,
        calls: list[ParsedCall],
    ) -> None:
        """Recursively collect call expressions."""
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = content[func_node.start_byte:func_node.end_byte]
                calls.append(
                    ParsedCall(
                        caller=context_name,
                        callee=callee,
                        line=node.start_point[0] + 1,
                    )
                )
        for child in node.children:
            self._collect_calls(child, content, context_name, calls)