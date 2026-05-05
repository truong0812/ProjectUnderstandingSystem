"""TypeScript parser using tree-sitter.

Extracts functions, classes, interfaces, methods, imports, and calls from TypeScript source.
"""

from __future__ import annotations

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser

from project_understanding.ingest.parser_base import (
    ParsedCall,
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    compute_symbol_hash,
    extract_docstring,
)


class TypeScriptParser:
    """Tree-sitter based parser for TypeScript source code."""

    def __init__(self, tsx: bool = False) -> None:
        if tsx:
            self._language = Language(tstypescript.language_tsx())
        else:
            self._language = Language(tstypescript.language_typescript())
        self._parser = Parser(self._language)

    def parse(self, file_path: str, content: str) -> ParsedFile:
        """Parse TypeScript source code and extract symbols, imports, calls."""
        tree = self._parser.parse(content.encode("utf-8"))
        root = tree.root_node

        result = ParsedFile(file_path=file_path, language="typescript")
        self._walk_node(root, content, result, parent_path="")

        return result

    def _walk_node(
        self,
        node: Node,
        content: str,
        result: ParsedFile,
        parent_path: str = "",
    ) -> None:
        """Recursively walk the tree-sitter AST."""
        if node.type == "import_statement":
            imp = self._parse_import(node, content)
            if imp:
                result.imports.append(imp)

        elif node.type == "import_clause":
            pass  # Handled by import_statement

        elif node.type == "function_declaration":
            symbol = self._parse_function(node, content, parent_path)
            result.symbols.append(symbol)
            # Extract calls
            calls = self._extract_calls(node, content, symbol.name)
            result.calls.extend(calls)

        elif node.type == "arrow_function":
            # Only capture top-level named arrow functions
            pass  # Arrow functions are handled via variable_declarator

        elif node.type == "class_declaration":
            symbol = self._parse_class(node, content, parent_path, result)
            result.symbols.append(symbol)

        elif node.type == "interface_declaration":
            symbol = self._parse_interface(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "type_alias_declaration":
            symbol = self._parse_type_alias(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "enum_declaration":
            symbol = self._parse_enum(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "export_statement":
            for child in node.children:
                if child.type in (
                    "function_declaration",
                    "class_declaration",
                    "interface_declaration",
                    "type_alias_declaration",
                    "enum_declaration",
                ):
                    self._walk_node(child, content, result, parent_path)
                elif child.type == "variable_declaration":
                    self._walk_node(child, content, result, parent_path)
                elif child.type == "lexical_declaration":
                    self._walk_node(child, content, result, parent_path)

        elif node.type == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    sym = self._try_parse_variable(child, content, parent_path, result)
                    if sym:
                        result.symbols.append(sym)

        elif node.type == "variable_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    sym = self._try_parse_variable(child, content, parent_path, result)
                    if sym:
                        result.symbols.append(sym)

        elif node.type == "method_definition":
            symbol = self._parse_method(node, content, parent_path)
            result.symbols.append(symbol)
            calls = self._extract_calls(node, content, symbol.name)
            result.calls.extend(calls)

        elif node.type in ("public_field_definition", "field_definition"):
            symbol = self._parse_field(node, content, parent_path)
            if symbol:
                result.symbols.append(symbol)

        # Recurse
        if node.type not in ("class_declaration", "class_body"):
            for child in node.children:
                self._walk_node(child, content, result, parent_path)

    def _parse_import(self, node: Node, content: str) -> ParsedImport | None:
        """Parse an import statement."""
        module_path = ""
        names: list[str] = []

        for child in node.children:
            if child.type == "string":
                # Module path (remove quotes)
                module_path = content[child.start_byte:child.end_byte].strip("\"'`")
            elif child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "identifier":
                        names.append(content[clause_child.start_byte:clause_child.end_byte])
                    elif clause_child.type == "named_imports":
                        for spec in clause_child.children:
                            if spec.type == "import_specifier":
                                for spec_child in spec.children:
                                    if spec_child.type == "identifier":
                                        names.append(
                                            content[spec_child.start_byte:spec_child.end_byte]
                                        )
                                        break
                    elif clause_child.type == "namespace_import":
                        for ns_child in clause_child.children:
                            if ns_child.type == "identifier":
                                names.append(
                                    "* as " + content[ns_child.start_byte:ns_child.end_byte]
                                )

        return ParsedImport(
            module_path=module_path,
            names=names,
            is_from_import=bool(module_path),
            line=node.start_point[0] + 1,
        )

    def _parse_function(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol:
        """Parse a function declaration."""
        name = ""
        params: list[str] = []
        return_type = ""
        is_async = False
        is_exported = False

        for child in node.children:
            if child.type == "identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "call_signature" or child.type == "formal_parameters":
                params = self._extract_parameters(child, content)
            elif child.type == "type_annotation":
                return_type = content[child.start_byte:child.end_byte].strip(": ")
            elif child.type == "async":
                is_async = True
            elif child.type == "export":
                is_exported = True

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)
        visibility = "public" if is_exported else "public"

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
        """Parse a class declaration."""
        name = ""
        bases: list[str] = []
        implements: list[str] = []
        is_abstract = False

        for child in node.children:
            if child.type == "type_identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        for ext_child in heritage_child.children:
                            if ext_child.type in ("type_identifier", "generic_type"):
                                bases.append(
                                    content[ext_child.start_byte:ext_child.end_byte]
                                )
                    elif heritage_child.type == "implements_clause":
                        for impl_child in heritage_child.children:
                            if impl_child.type in ("type_identifier", "generic_type"):
                                implements.append(
                                    content[impl_child.start_byte:impl_child.end_byte]
                                )
            elif child.type == "abstract":
                is_abstract = True

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Parse class body for methods
        methods: list[ParsedSymbol] = []
        for child in node.children:
            if child.type == "class_body":
                for member in child.children:
                    if member.type == "method_definition":
                        method = self._parse_method(member, content, qual_path)
                        methods.append(method)
                    elif member.type in ("public_field_definition", "field_definition"):
                        field = self._parse_field(member, content, qual_path)
                        if field:
                            methods.append(field)
                    elif member.type == "constructor":
                        ctor = self._parse_constructor(member, content, qual_path)
                        methods.append(ctor)

        return ParsedSymbol(
            name=name,
            kind="class",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
            parameters=[],
            return_type="",
            docstring=doc,
            children=methods,
        )

    def _parse_method(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse a method definition inside a class."""
        name = ""
        params: list[str] = []
        return_type = ""
        is_async = False
        is_static = False
        visibility = "public"

        for child in node.children:
            if child.type == "property_identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "formal_parameters":
                params = self._extract_parameters(child, content)
            elif child.type == "type_annotation":
                return_type = content[child.start_byte:child.end_byte].strip(": ")
            elif child.type == "async":
                is_async = True
            elif child.type == "static":
                is_static = True
            elif child.type == "accessibility_modifier":
                mod = content[child.start_byte:child.end_byte]
                visibility = mod  # public, private, protected

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        return ParsedSymbol(
            name=name,
            kind="method",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            is_async=is_async,
            is_static=is_static,
            parameters=params,
            return_type=return_type,
            docstring=doc,
        )

    def _parse_constructor(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse a constructor definition."""
        params: list[str] = []

        for child in node.children:
            if child.type == "formal_parameters":
                params = self._extract_parameters(child, content)

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.constructor" if parent_path else "constructor"
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name="constructor",
            kind="constructor",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
            parameters=params,
        )

    def _parse_field(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol | None:
        """Parse a field/property definition in a class."""
        name = ""
        for child in node.children:
            if child.type == "property_identifier" and not name:
                name = content[child.start_byte:child.end_byte]

        if not name:
            return None

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name=name,
            kind="property",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
        )

    def _parse_interface(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse an interface declaration."""
        name = ""
        for child in node.children:
            if child.type == "type_identifier" and not name:
                name = content[child.start_byte:child.end_byte]

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        return ParsedSymbol(
            name=name,
            kind="interface",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
            docstring=doc,
        )

    def _parse_type_alias(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse a type alias declaration."""
        name = ""
        for child in node.children:
            if child.type == "type_identifier" and not name:
                name = content[child.start_byte:child.end_byte]

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name=name,
            kind="type",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
        )

    def _parse_enum(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse an enum declaration."""
        name = ""
        for child in node.children:
            if child.type == "identifier" and not name:
                name = content[child.start_byte:child.end_byte]

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name=name,
            kind="enum",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility="public",
        )

    def _try_parse_variable(
        self, node: Node, content: str, parent_path: str, result: ParsedFile
    ) -> ParsedSymbol | None:
        """Try to parse a variable declaration (may be an arrow function or constant)."""
        name = ""
        is_arrow_func = False
        const_name = False

        for child in node.children:
            if child.type == "identifier" and not name:
                name = content[child.start_byte:child.end_byte]
            elif child.type == "arrow_function":
                is_arrow_func = True
            elif child.type in ("string", "number", "template_string"):
                const_name = True

        if not name:
            return None

        # Check if arrow function
        if is_arrow_func:
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            qual_path = f"{parent_path}.{name}" if parent_path else name
            symbol_hash = compute_symbol_hash(content, line_start, line_end)
            return ParsedSymbol(
                name=name,
                kind="function",
                path=qual_path,
                line_start=line_start,
                line_end=line_end,
                hash=symbol_hash,
                visibility="public",
            )

        # Check for constant (UPPER_CASE)
        if name.isupper() or const_name:
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            qual_path = f"{parent_path}.{name}" if parent_path else name
            symbol_hash = compute_symbol_hash(content, line_start, line_end)
            return ParsedSymbol(
                name=name,
                kind="constant",
                path=qual_path,
                line_start=line_start,
                line_end=line_end,
                hash=symbol_hash,
                visibility="public",
            )

        return None

    def _extract_parameters(self, params_node: Node, content: str) -> list[str]:
        """Extract parameter names from parameter list."""
        params: list[str] = []
        for child in params_node.children:
            if child.type == "required_parameter" or child.type == "optional_parameter":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append(content[sub.start_byte:sub.end_byte])
                        break
                    elif sub.type == "rest_parameter":
                        for rest_sub in sub.children:
                            if rest_sub.type == "identifier":
                                params.append(
                                    "..." + content[rest_sub.start_byte:rest_sub.end_byte]
                                )
            elif child.type == "identifier":
                params.append(content[child.start_byte:child.end_byte])
            elif child.type == "rest_parameter":
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append("..." + content[sub.start_byte:sub.end_byte])
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
        if node.type == "call_expression":
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