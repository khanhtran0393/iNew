"""Compare original source/app vs reconstructed d:\iNew\app at AST level."""
import ast
import os

SRC = r"d:\iNew\source\app"
NEW = r"d:\iNew\app"


def collect(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except Exception as e:
        return None, "PARSE_ERROR: %s" % e
    funcs = set()
    classes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
    return (funcs, classes), None


def rel_files(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".venv")]
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace("\\", "/")
                out[rel] = full
    return out


src_files = rel_files(SRC)
new_files = rel_files(NEW)

print("=" * 78)
print("MODULES PRESENT IN ORIGINAL BUT MISSING IN RECONSTRUCTION")
print("=" * 78)
for rel in sorted(src_files):
    if rel not in new_files:
        print("  MISSING MODULE: %s" % rel)

print()
print("=" * 78)
print("FUNCTION / CLASS DIFFERENCES (per module)")
print("=" * 78)
for rel in sorted(src_files):
    if rel not in new_files:
        continue
    s, serr = collect(src_files[rel])
    n, nerr = collect(new_files[rel])
    if serr or nerr:
        print("  !! %s: src=%s new=%s" % (rel, serr, nerr))
        continue
    sf, sc = s
    nf, nc = n
    lost_f = sorted(sf - nf)
    lost_c = sorted(sc - nc)
    gained_f = sorted(nf - sf)
    if lost_f or lost_c:
        print("")
        print("### %s" % rel)
        if lost_f:
            print("    LOST FUNCTIONS : %s" % lost_f)
        if lost_c:
            print("    LOST CLASSES   : %s" % lost_c)
        if gained_f:
            print("    added funcs    : %s" % gained_f)

print()
print("=" * 78)
print("MODULES ONLY IN RECONSTRUCTION")
print("=" * 78)
for rel in sorted(new_files):
    if rel not in src_files:
        print("  NEW: %s" % rel)
