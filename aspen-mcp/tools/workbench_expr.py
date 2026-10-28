"""Arithmetic for workbench programs: safe expressions over the program's variables.

An expression is Python-like arithmetic, parsed with ``ast`` and evaluated by walking
the tree, so only what is listed here can run -- no attribute access, no imports, no
names beyond the program's variables, a few constants and the functions below.

  + - * / // %  ** or ^ (power)   comparisons   and or not   a if cond else b
  abs min max round sum mean sqrt exp log ln log10 log2 sin cos tan asin acos atan
  atan2 sinh cosh tanh floor ceil pow hypot sign clamp   pi e inf

Programs add their own functions with ``def`` statements: ``f(x, y) = x*y/2``.

A variable without a value (a read that failed, a run that errored) makes the whole
result "no value" instead of an error, so a sweep that crosses a failed point records a
gap and carries on. Syntax errors and unknown functions are errors: they are mistakes in
the program, and a dry run reports them before anything runs.
"""

from __future__ import annotations

import ast
import math
import operator as op

MAX_LEN = 500
MAX_DEPTH = 40
MAX_STEPS = 10_000      # evaluation steps per expression, calls into program functions included


class ExprError(ValueError):
    """The expression itself is wrong: bad syntax, unknown function, wrong arguments."""


class NoValue(Exception):
    """A value the expression needs is missing, or the arithmetic has no answer."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


def _mean(*a):
    return sum(a) / len(a)


FUNCS = {
    "abs": abs, "min": min, "max": max, "round": round, "sum": lambda *a: sum(a), "mean": _mean,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log, "ln": math.log, "log10": math.log10,
    "log2": math.log2, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin,
    "acos": math.acos, "atan": math.atan, "atan2": math.atan2, "sinh": math.sinh,
    "cosh": math.cosh, "tanh": math.tanh, "floor": math.floor, "ceil": math.ceil,
    "pow": math.pow, "hypot": math.hypot, "sign": lambda x: float((x > 0) - (x < 0)),
    "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
}
CONSTS = {"pi": math.pi, "e": math.e, "inf": math.inf}

_BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow}
_UNARY = {ast.USub: op.neg, ast.UAdd: op.pos, ast.Not: op.not_}
_CMP = {ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge, ast.Eq: op.eq, ast.NotEq: op.ne}
_NAME = __import__("re").compile(r"^[A-Za-z_]\w*$")


def is_name(text: str) -> bool:
    return bool(_NAME.match(text or ""))


def parse(text, funcs: dict | None = None) -> ast.AST:
    """Parse and check an expression. ``funcs`` names the program's own functions."""
    # ^ is power, as engineers write it; as Python's XOR it would bind looser than +
    text = str(text if text is not None else "").strip().replace("^", "**")
    if not text:
        raise ExprError("empty expression")
    if len(text) > MAX_LEN:
        raise ExprError(f"expression longer than {MAX_LEN} characters")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"syntax error in '{text}': {exc.msg}") from None
    except (RecursionError, MemoryError):
        raise ExprError("expression is nested too deeply") from None
    user = funcs or {}
    try:
        nodes = list(ast.walk(tree))
    except (RecursionError, MemoryError):
        raise ExprError("expression is nested too deeply") from None
    for node in nodes:
        if isinstance(node, (ast.Expression, ast.Load, ast.boolop, ast.operator, ast.unaryop, ast.cmpop)):
            if isinstance(node, ast.operator) and type(node) not in _BIN:
                raise ExprError(f"operator {type(node).__name__} is not allowed")
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ExprError(f"only numbers are allowed, not {node.value!r}")
            continue
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Name)):
            continue
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ExprError("only plain function calls like sqrt(x) are allowed")
            name = node.func.id
            if name not in FUNCS and name not in user:
                raise ExprError(f"unknown function {name}()")
            if name in user and len(node.args) != len(user[name][0]):
                raise ExprError(f"{name}() takes {len(user[name][0])} arguments, got {len(node.args)}")
            continue
        raise ExprError(f"'{ast.unparse(node) if hasattr(ast, 'unparse') else type(node).__name__}' is not allowed")
    return tree


def names(tree: ast.AST) -> set[str]:
    """Variable names an expression reads (function names excluded)."""
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)}
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in called}


def evaluate(tree: ast.AST, env: dict, funcs: dict | None = None, _depth: int = 0,
             _steps: list | None = None) -> float:
    """Value of a parsed expression. Raises NoValue when an input is missing or the
    arithmetic has no answer (division by zero, log of a negative, overflow), ExprError
    when it takes more than MAX_STEPS steps (``f(x) = f(x) + f(x)`` would never end)."""
    funcs = funcs or {}
    if _depth > MAX_DEPTH:
        raise ExprError("functions call each other too deeply")
    steps = _steps if _steps is not None else [0]      # shared by every nested call

    def ev(node):
        steps[0] += 1
        if steps[0] > MAX_STEPS:
            raise ExprError(f"expression takes more than {MAX_STEPS} steps to evaluate")
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in env:
                v = env[node.id]
                if v is None:
                    raise NoValue(f"{node.id} has no value")
                return float(v)
            if node.id in CONSTS:
                return CONSTS[node.id]
            raise NoValue(f"{node.id} has no value")
        if isinstance(node, ast.BinOp):
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp):
            return float(_UNARY[type(node.op)](ev(node.operand)))
        if isinstance(node, ast.BoolOp):
            vals = [ev(v) for v in node.values]
            return float(all(vals) if isinstance(node.op, ast.And) else any(vals))
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for o, right in zip(node.ops, node.comparators):
                r = ev(right)
                if not _CMP[type(o)](left, r):
                    return 0.0
                left = r
            return 1.0
        if isinstance(node, ast.IfExp):
            return ev(node.body) if ev(node.test) else ev(node.orelse)
        if isinstance(node, ast.Call):
            args = [ev(a) for a in node.args]
            name = node.func.id
            if name in funcs:
                params, body = funcs[name]
                return evaluate(body, dict(env, **dict(zip(params, args))), funcs, _depth + 1, steps)
            return float(FUNCS[name](*args))
        raise ExprError(f"cannot evaluate {type(node).__name__}")

    try:
        v = ev(tree)
    except ZeroDivisionError:
        raise NoValue("division by zero") from None
    except OverflowError:
        raise NoValue("the result is too large") from None
    except (RecursionError, MemoryError):
        raise ExprError("expression is nested too deeply") from None
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ExprError):
            raise
        raise NoValue(f"no answer ({exc})") from None
    if isinstance(v, complex) or not math.isfinite(v) and not math.isinf(v):
        raise NoValue("the result is not a real number")
    return v
