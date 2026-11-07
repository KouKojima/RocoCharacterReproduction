"""List the BasePass program variants of a cooked material with instruction counts."""
import json
import pathlib
import sys

SHADERS = pathlib.Path(sys.argv[1])
PREFIXES = sys.argv[2:]

inv = json.loads((SHADERS / 'inventory.json').read_text(encoding='utf8'))

SKIP_PREFIX = ('dcl_', 'ps_', 'vs_', '//', 'ret', 'Approximately', 'setp_', 'resource_')


def instruction_count(asm_path):
    text = asm_path.read_text(encoding='utf8').splitlines()
    n = 0
    for line in text:
        s = line.strip()
        if not s or s.startswith(SKIP_PREFIX):
            continue
        n += 1
    return n


for prefix in PREFIXES:
    print('==', prefix)
    seen = set()
    for entry in inv:
        if entry['prefix'] != prefix:
            continue
        kind = str(entry.get('resolvedType', ''))
        if 'BasePass' not in kind:
            continue
        asm = SHADERS / (entry['file'] + '.asm')
        if not asm.exists():
            continue
        key = (kind, entry['file'])
        if key in seen:
            continue
        seen.add(key)
        print('  %5d  %s  %s' % (instruction_count(asm), entry['file'][:26], kind))
