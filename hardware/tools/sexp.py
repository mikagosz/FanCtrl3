"""Minimal S-expression reader/writer for KiCad files."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """Bare (unquoted) atom."""


def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        op, cl, qs, atom = m.groups()
        if op:
            stack.append(cur)
            cur = []
        elif cl:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(re.sub(r'\\(.)', lambda m: {'n': '\n'}.get(m.group(1), m.group(1)),
                              qs[1:-1]))
        else:
            cur.append(Sym(atom))
    return cur[0] if len(cur) == 1 else cur


def _atom(a):
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, (int, float)):
        return fmt(a)
    s = str(a).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    return f'"{s}"'


def fmt(v):
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def dump(e, indent=0):
    if not isinstance(e, list):
        return _atom(e)
    simple = all(not isinstance(x, list) for x in e)
    if simple:
        return "(" + " ".join(_atom(x) for x in e) + ")"
    pad = "\t" * (indent + 1)
    head = []
    rest = []
    for x in e:
        if not isinstance(x, list) and not rest:
            head.append(_atom(x))
        else:
            rest.append(x)
    out = "(" + " ".join(head)
    for x in rest:
        out += "\n" + pad + dump(x, indent + 1)
    return out + "\n" + "\t" * indent + ")"


def find(e, key):
    """First child list whose head is key."""
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def walk(e, key):
    """All descendant lists (depth-first) whose head is key."""
    if isinstance(e, list):
        if e and e[0] == key:
            yield e
        for x in e:
            yield from walk(x, key)
