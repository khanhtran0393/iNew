import marshal
import dis
import struct
import sys
from pathlib import Path

def read_pyz(path: str):
    with open(path, 'rb') as f:
        header = f.read(8)
        if header[:4] != b'PYZ\0':
            raise ValueError('Not a PYZ file')
        magic = header[4:8]
        # Python 3.13 magic: f3 0d 0d 0a (4 bytes)
        if magic != b'f3\x0d\x0d\x0a':
            raise ValueError(f'Unexpected Python version: {magic.hex()}')
        # Skip timestamp (4 bytes) and size (4 bytes)
        f.seek(16)
        toc_offset = struct.unpack('<I', f.read(4))[0]
        f.seek(toc_offset)
        toc_size = struct.unpack('<I', f.read(4))[0]
        toc_data = f.read(toc_size)
        toc = marshal.loads(toc_data)
        return toc

def extract_module(toc, target_name: str):
    for entry in toc['target']:
        if entry['module'] == target_name:
            return entry['data']
    return None

def write_pyc(data: bytes, path: str):
    with open(path, 'wb') as f:
        f.write(b'PYZ\0')
        f.write(struct.pack('<I', 0))  # timestamp
        f.write(struct.pack('<I', 0))  # size
        f.write(struct.pack('<I', 0))  # size of marshaled data
        f.write(data)

def disassemble_module(data: bytes, name: str):
    module = marshal.loads(data)
    for code_obj in module['code_objects']:
        if code_obj.co_name == name:
            print(f'=== DISASSEMBLY FOR {name} ===')
            for instr in dis.get_instructions(code_obj.co_code):
                print(f'{instr.offset:4d} {instr.opname:<25} {instr.argrepr}')
            return

if __name__ == '__main__':
    pyz_path = Path(r'D:\iNew\iNew.exe_extracted\PYZ.pyz')
    toc = read_pyz(str(pyz_path))
    ai_key_router_data = extract_module(toc, 'app.services.ai_key_router')
    if ai_key_router_data:
        write_pyc(ai_key_router_data, r'd:\iNew\ai_key_router.pyc')
        disassemble_module(ai_key_router_data, 'ai_key_router')
    else:
        print(f'Module {target_name} not found in PYZ')