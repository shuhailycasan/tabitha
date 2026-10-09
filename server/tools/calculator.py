import ast
import operator


# safe arithmetic evaluator — no names, no attributes, no imports
_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
def _avg(*xs):
    flat = xs[0] if len(xs) == 1 and isinstance(xs[0], list) else list(xs)
    return sum(flat) / len(flat)
_FUNCS = {"sum": sum, "min": min, "max": max, "abs": abs, "round": round, "avg": _avg}


def safe_eval(expr):
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.List):
            return [ev(e) for e in node.elts]
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
            fn = _FUNCS[node.func.id]
            args = [ev(a) for a in node.args]
            if fn in (sum, min, max):
                return fn(args[0] if len(args) == 1 and isinstance(args[0], list) else args)
            return fn(*args)
        raise ValueError(f"unsupported expression: {ast.dump(node)}")
    return ev(ast.parse(str(expr), mode="eval").body)
