"""Extract real modules from the original PyInstaller PYZ and dump disassembly.

PYZ layout (PyInstaller 5/6):
  0..3   b'PYZ\\0'
  4..7   python magic
  8..11  TOC offset (big endian int32)
  12..   compressed module blob (zlib per entry)
  TOC at toc_offset: marshalled dict {name: (typecode, offset, length)}
"""
import dis
import marshal
import struct
import sys
import types
import zlib
from pathlib import Path

PYZ = Path(r'D:\iNew\iNew.exe_extracted\PYZ.pyz')
OUT = Path(r'D:\iNew\_disasm')


def load_toc():
    data = PYZ.read_bytes()
    assert data[:4] == b'PYZ\0', data[:8]
    toc_offset = struct.unpack('!i', data[8:12])[0]
    toc = None
    errors = []
    for skip in (0, 4):
        for enc in ('!I', '<I'):
            try:
                length = struct.unpack(enc, data[toc_offset + skip:toc_offset + skip + 4])[0]
                candidate = marshal.loads(data[toc_offset + skip + 4:toc_offset + skip + 4 + length])
                if isinstance(candidate, dict):
                    toc = candidate
                    break
            except Exception as exc:
                errors.append(f'skip={skip} enc={enc}: {exc}')
        if toc is not None:
            break
    if toc is None:
        # last resort: unmarshalled dict directly at offset
        try:
            toc = marshal.loads(data[toc_offset:])
        except Exception as exc:
            errors.append(f'direct: {exc}')
    if toc is None:
        raise SystemExit('TOC parse failed:\n' + '\n'.join(errors))
    return data, toc


def get_code(data, toc, modname):
    if isinstance(toc, dict):
        entry = toc.get(modname)
    elif isinstance(toc, list):
        entry = None
        for name, e in toc:
            if name == modname:
                entry = e
                break
    else:
        return None, f'UNEXPECTED TOC TYPE {type(toc)}'
    if entry is None:
        return None, f'NOT IN TOC (sample keys: {list(toc)[:5] if isinstance(toc, dict) else [n for n,_ in list(toc)[:5]]})'
    # debug
    debug_path = Path(r'D:\iNew\_disasm') / f'{modname.replace(".", "__")}_entry.txt'
    debug_path.write_text(repr(entry), encoding='utf-8')
    try:
        typecode, offset, length = entry
    except (TypeError, ValueError):
        try:
            offset, length = entry
            typecode = b'z'
        except (TypeError, ValueError):
            return None, f'UNEXPECTED ENTRY SHAPE {entry!r}'
    blob = data[12 + offset: 12 + offset + length]
    # save raw blob
    (Path(r'D:\iNew\_disasm') / f'{modname.replace(".", "__")}_blob.bin').write_bytes(blob)
    if typecode in (b'z', b'Z'):
        try:
            blob = zlib.decompress(blob)
        except zlib.error:
            pass
    # If it looks like a .pyc file (starts with magic), skip header
    if blob[:4] in (b'\xf3\r\r\n', b'\x03\xf3\r\r', b'\xcb\r\r\n', b'\xca\r\r\n'):
        blob = blob[16:]  # skip magic+timestamp+size (16 bytes for 3.7+)
    try:
        return marshal.loads(blob), None
    except Exception as exc:
        # try reading from offset 0 after possible .pyc header
        try:
            return marshal.loads(blob[16:]), None
        except Exception:
            pass
        return None, f'marshal failed: {exc}'


def walk(code, depth=0, out=None):
    if out is None:
        out = []
    out.append((depth, code))
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            walk(const, depth + 1, out)
    return out


def dump(modname):
    data, toc = load_toc()
    code, err = get_code(data, toc, modname)
    if code is None:
        return f'!! {modname}: {err}'
    OUT.mkdir(exist_ok=True)
    lines = []
    lines.append(f'### MODULE {modname}')
    lines.append(f'### module names: {code.co_names}')
    lines.append(f'### module consts: {[c for c in code.co_consts if not isinstance(c, types.CodeType)]}')
    for depth, co in walk(code):
        lines.append('')
        lines.append(f'--- {"  " * depth}CODE {co.co_name} args={co.co_varnames[:co.co_argcount]} names={co.co_names}')
        lines.append(f'    consts={[c for c in co.co_consts if not isinstance(c, types.CodeType)]}')
        lines.append(f'    varnames={co.co_varnames} freevars={co.co_freevars} cellvars={co.co_cellvars}')
        for ins in dis.get_instructions(co.co_code):
            lines.append(f'    {ins.offset:5d} {ins.opname:<28} {ins.argrepr}')
    safe = modname.replace('.', '__')
    path = OUT / (safe + '.txt')
    path.write_text('\n'.join(lines), encoding='utf-8')
    return f'== {modname} -> {path} ({len(lines)} lines)'


if __name__ == '__main__':
    data, toc = load_toc()
    report = [f'TOC entries: {len(toc)}']
    sample = list(toc)[:5]
    report.append(f'sample: {sample}')
    Path(r'D:\iNew\_disasm').mkdir(exist_ok=True)
    targets = sys.argv[1:] or [
        'app.services.ai_key_router',
        'app.services.runtime_config',
        'app.services.security_crypto',
    ]
    for t in targets:
        report.append(dump(t))
    Path(r'D:\iNew\_pyz_report.txt').write_text('\n'.join(report), encoding='utf-8')
    print('\n'.join(report))