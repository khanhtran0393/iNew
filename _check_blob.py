import zlib, marshal, types
from pathlib import Path

def test(name):
    blob = Path(rf'D:\iNew\_disasm\{name}_blob.bin').read_bytes()
    print(f'\n=== {name} ===')
    print(f'len: {len(blob)}')
    print(f'hex: {blob[:20].hex()}')
    
    # Try direct marshal
    for skip in (0, 16):
        if len(blob) <= skip:
            continue
        try:
            obj = marshal.loads(blob[skip:])
            print(f'  marshal @{skip}: type={type(obj).__name__}', end='')
            if isinstance(obj, types.CodeType):
                print(f' name={obj.co_name}')
            else:
                print()
        except Exception as e:
            print(f'  marshal @{skip}: {e}')
    
    # Try zlib decompress then marshal
    try:
        dec = zlib.decompress(blob)
        print(f'  zlib: ok len={len(dec)}')
        for skip in (0, 16):
            if len(dec) <= skip:
                continue
            try:
                obj = marshal.loads(dec[skip:])
                print(f'  marshal @{skip} after zlib: type={type(obj).__name__}', end='')
                if isinstance(obj, types.CodeType):
                    print(f' name={obj.co_name}')
                else:
                    print()
            except Exception as e:
                print(f'  marshal @{skip} after zlib: {e}')
    except Exception as e:
        print(f'  zlib: {e}')

test('app__services__ai_key_router')
test('app__services__runtime_config')
test('app__services__security_crypto')