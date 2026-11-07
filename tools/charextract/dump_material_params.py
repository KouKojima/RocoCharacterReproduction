"""Dump the scalar/vector parameter overrides stored on a cooked material instance."""
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
obj = json.loads(path.read_text(encoding='utf8'))[0]
props = obj.get('Properties', {})
for field in ('ScalarParameterValues', 'VectorParameterValues', 'TextureParameterValues'):
    rows = props.get(field, [])
    print('=== %s (%d) ===' % (field, len(rows)))
    for row in rows:
        info = row['ParameterInfo']
        value = row.get('ParameterValue')
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k in ('X', 'Y', 'Z', 'W', 'Value')}
        print('  %-28s assoc=%-6s idx=%s  %s' % (info['Name'], info.get('Association'), info.get('Index'), value))
