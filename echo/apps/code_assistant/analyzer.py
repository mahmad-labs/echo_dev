from __future__ import annotations
import ast
from dataclasses import dataclass

@dataclass(frozen=True)
class AnalysisResult:
    valid: bool
    symbols: tuple[str,...]
    errors: tuple[str,...]

class PythonAnalyzer:
    def analyze(self,source):
        try: tree=ast.parse(source)
        except SyntaxError as exc: return AnalysisResult(False,(),(f'{exc.msg} at line {exc.lineno}',))
        symbols=tuple(node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)))
        return AnalysisResult(True,symbols,())
