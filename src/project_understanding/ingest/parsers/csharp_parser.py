"""C# parser using tree-sitter.

Extracts classes, interfaces, structs, methods, properties, enums, namespaces,
imports, and calls from C# source code.
"""

from __future__ import annotations

import tree_sitter_c_sharp as tscs
from tree_sitter import Language, Node, Parser

from project_understanding.ingest.parser_base import (
    ParsedCall,
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    compute_symbol_hash,
    extract_docstring,
)


class CSharpParser:
    """Tree-sitter based parser for C# source code."""

    def __init__(self) -> None:
        self._language = Language(tscs.language())
        self._parser = Parser(self._language)

    def parse(self, file_path: str, content: str) -> ParsedFile:
        """Parse C# source code and extract symbols, imports, calls."""
        tree = self._parser.parse(content.encode("utf-8"))
        root = tree.root_node

        result = ParsedFile(file_path=file_path, language="c_sharp")
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
        if node.type == "using_directive":
            imp = self._parse_using(node, content)
            if imp:
                result.imports.append(imp)

        elif node.type == "namespace_declaration":
            ns_name = self._get_child_text(node, "identifier", content)
            new_path = f"{parent_path}.{ns_name}" if parent_path else ns_name
            for child in node.children:
                self._walk_node(child, content, result, new_path)
            return  # Don't recurse further here

        elif node.type == "class_declaration":
            symbol = self._parse_class(node, content, parent_path, result)
            result.symbols.append(symbol)

        elif node.type == "interface_declaration":
            symbol = self._parse_interface(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "struct_declaration":
            symbol = self._parse_struct(node, content, parent_path, result)
            result.symbols.append(symbol)

        elif node.type == "enum_declaration":
            symbol = self._parse_enum(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "delegate_declaration":
            symbol = self._parse_delegate(node, content, parent_path)
            result.symbols.append(symbol)

        elif node.type == "method_declaration":
            symbol = self._parse_method(node, content, parent_path)
            result.symbols.append(symbol)
            calls = self._extract_calls(node, content, symbol.name)
            result.calls.extend(calls)

        elif node.type == "constructor_declaration":
            symbol = self._parse_constructor(node, content, parent_path)
            result.symbols.append(symbol)
            calls = self._extract_calls(node, content, symbol.name)
            result.calls.extend(calls)

        elif node.type == "property_declaration":
            symbol = self._parse_property(node, content, parent_path)
            if symbol:
                result.symbols.append(symbol)

        elif node.type == "field_declaration":
            symbol = self._parse_field_declaration(node, content, parent_path)
            if symbol:
                result.symbols.append(symbol)

        # Recurse into children
        if node.type not in ("class_declaration", "struct_declaration", "interface_declaration"):
            for child in node.children:
                self._walk_node(child, content, result, parent_path)

    def _get_child_text(self, node: Node, child_type: str, content: str) -> str:
        """Get text content of a child node by type."""
        for child in node.children:
            if child.type == child_type:
                return content[child.start_byte:child.end_byte]
        return ""

    def _get_modifiers(self, node: Node, content: str) -> list[str]:
        """Extract access and other modifiers from a declaration."""
        modifiers: list[str] = []
        for child in node.children:
            if child.type in (
                "public",
                "private",
                "protected",
                "internal",
                "static",
                "async",
                "abstract",
                "virtual",
                "override",
                "sealed",
                "readonly",
                "const",
                "new",
            ):
                modifiers.append(content[child.start_byte:child.end_byte])
            elif child.type == "modifier":
                modifiers.append(content[child.start_byte:child.end_byte])
        return modifiers

    def _get_visibility(self, modifiers: list[str]) -> str:
        """Determine visibility from modifiers."""
        for mod in modifiers:
            if mod in ("public", "private", "protected", "internal"):
                return mod
        return "private"  # C# default

    def _parse_using(self, node: Node, content: str) -> ParsedImport | None:
        """Parse a using directive."""
        module_path = ""
        for child in node.children:
            if child.type == "identifier":
                module_path = content[child.start_byte:child.end_byte]
            elif child.type == "qualified_name":
                module_path = content[child.start_byte:child.end_byte]
            elif child.type == "name_equals":
                # using Alias = Namespace;
                module_path = content[child.start_byte:child.end_byte]

        return ParsedImport(
            module_path=module_path,
            names=[],
            is_from_import=False,
            line=node.start_point[0] + 1,
        )

    def _parse_class(
        self,
        node: Node,
        content: str,
        parent_path: str,
        result: ParsedFile,
    ) -> ParsedSymbol:
        """Parse a class declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        is_static = "static" in modifiers

        # Find base type and interfaces
        bases: list[str] = []
        for child in node.children:
            if child.type == "base_list":
                for base_child in child.children:
                    if base_child.type in ("identifier", "qualified_name", "generic_name"):
                        bases.append(content[base_child.start_byte:base_child.end_byte])

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Parse class body
        members: list[ParsedSymbol] = []
        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "method_declaration":
                        m = self._parse_method(member, content, qual_path)
                        members.append(m)
                        calls = self._extract_calls(member, content, m.name)
                        result.calls.extend(calls)
                    elif member.type == "constructor_declaration":
                        m = self._parse_constructor(member, content, qual_path)
                        members.append(m)
                        calls = self._extract_calls(member, content, m.name)
                        result.calls.extend(calls)
                    elif member.type == "property_declaration":
                        m = self._parse_property(member, content, qual_path)
                        if m:
                            members.append(m)
                    elif member.type == "field_declaration":
                        m = self._parse_field_declaration(member, content, qual_path)
                        if m:
                            members.append(m)
                    elif member.type == "class_declaration":
                        m = self._parse_class(member, content, qual_path, result)
                        members.append(m)
                    elif member.type == "enum_declaration":
                        m = self._parse_enum(member, content, qual_path)
                        members.append(m)
                    elif member.type == "interface_declaration":
                        m = self._parse_interface(member, content, qual_path)
                        members.append(m)
                    elif member.type == "struct_declaration":
                        m = self._parse_struct(member, content, qual_path, result)
                        members.append(m)

        return ParsedSymbol(
            name=name,
            kind="class",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            is_static=is_static,
            docstring=doc,
            children=members,
        )

    def _parse_interface(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse an interface declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Parse interface members
        members: list[ParsedSymbol] = []
        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "method_declaration":
                        m = self._parse_method(member, content, qual_path)
                        members.append(m)
                    elif member.type == "property_declaration":
                        m = self._parse_property(member, content, qual_path)
                        if m:
                            members.append(m)

        return ParsedSymbol(
            name=name,
            kind="interface",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            docstring=doc,
            children=members,
        )

    def _parse_struct(
        self,
        node: Node,
        content: str,
        parent_path: str,
        result: ParsedFile,
    ) -> ParsedSymbol:
        """Parse a struct declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)
        doc = extract_docstring(content, line_start)

        # Parse struct body
        members: list[ParsedSymbol] = []
        for child in node.children:
            if child.type == "declaration_list":
                for member in child.children:
                    if member.type == "method_declaration":
                        members.append(self._parse_method(member, content, qual_path))
                    elif member.type == "constructor_declaration":
                        members.append(self._parse_constructor(member, content, qual_path))
                    elif member.type == "property_declaration":
                        m = self._parse_property(member, content, qual_path)
                        if m:
                            members.append(m)
                    elif member.type == "field_declaration":
                        m = self._parse_field_declaration(member, content, qual_path)
                        if m:
                            members.append(m)

        return ParsedSymbol(
            name=name,
            kind="struct",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            docstring=doc,
            children=members,
        )

    def _parse_enum(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse an enum declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)

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
            visibility=visibility,
        )

    def _parse_delegate(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse a delegate declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        params = self._extract_parameters(node, content)

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name=name,
            kind="delegate",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            parameters=params,
        )

    def _parse_method(self, node: Node, content: str, parent_path: str) -> ParsedSymbol:
        """Parse a method declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        is_async = "async" in modifiers
        is_static = "static" in modifiers

        params = self._extract_parameters(node, content)
        return_type = self._get_return_type(node, content)

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
        """Parse a constructor declaration."""
        name = self._get_child_text(node, "identifier", content)
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        params = self._extract_parameters(node, content)

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        return ParsedSymbol(
            name=name,
            kind="constructor",
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            parameters=params,
        )

    def _parse_property(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol | None:
        """Parse a property declaration."""
        name = self._get_child_text(node, "identifier", content)
        if not name:
            return None

        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        is_static = "static" in modifiers

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
            visibility=visibility,
            is_static=is_static,
        )

    def _parse_field_declaration(
        self, node: Node, content: str, parent_path: str
    ) -> ParsedSymbol | None:
        """Parse a field declaration."""
        modifiers = self._get_modifiers(node, content)
        visibility = self._get_visibility(modifiers)
        is_static = "static" in modifiers

        # Find the variable declarator
        name = ""
        for child in node.children:
            if child.type == "variable_declaration":
                for var_child in child.children:
                    if var_child.type == "variable_declarator":
                        for decl_child in var_child.children:
                            if decl_child.type == "identifier" and not name:
                                name = content[decl_child.start_byte:decl_child.end_byte]
                                break

        if not name:
            return None

        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1
        qual_path = f"{parent_path}.{name}" if parent_path else name
        symbol_hash = compute_symbol_hash(content, line_start, line_end)

        kind = "constant" if "const" in modifiers else "field"

        return ParsedSymbol(
            name=name,
            kind=kind,
            path=qual_path,
            line_start=line_start,
            line_end=line_end,
            hash=symbol_hash,
            visibility=visibility,
            is_static=is_static,
        )

    def _extract_parameters(self, node: Node, content: str) -> list[str]:
        """Extract parameter names from parameter list."""
        params: list[str] = []
        for child in node.children:
            if child.type == "parameter_list":
                for param in child.children:
                    if param.type == "parameter":
                        for param_child in param.children:
                            if param_child.type == "identifier":
                                # Get the last identifier (parameter name, not type)
                                name = content[param_child.start_byte:param_child.end_byte]
                                params.append(name)
                                break
        return params

    def _get_return_type(self, node: Node, content: str) -> str:
        """Get the return type of a method."""
        for child in node.children:
            if child.type == "type":
                return content[child.start_byte:child.end_byte]
            elif child.type in ("void_keyword", "predefined_type"):
                return content[child.start_byte:child.end_byte]
        return ""

    def _extract_calls(
        self, node: Node, content: str, context_name: str
    ) -> list[ParsedCall]:
        """Extract method calls from a node."""
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
        """Recursively collect invocation expressions."""
        if node.type == "invocation_expression":
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