"""Pack the multi-character preview into one offline HTML file.

Local helper (not part of the handoff bundle). Same archive layout as the
kit's pack_character_preview.py, but includes every per-character asset folder.
"""
from pathlib import Path
import argparse, json, gzip, base64, hashlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='preview root containing preview/')
    parser.add_argument('--code', type=Path, required=True, help='folder with index.html and app.bundle.js')
    parser.add_argument('--out', type=Path, default=None)
    options = parser.parse_args()
    root = options.data.resolve()
    preview = root / 'preview'
    code = options.code.resolve()

    paths = []
    for item in sorted(preview.rglob('*')):
        if not item.is_file():
            continue
        rel = item.relative_to(preview).as_posix()
        if rel in ('index.html', 'app.bundle.js'):
            continue
        if item.suffix in ('.bin', '.json', '.rgba'):
            paths.append(rel)

    files, data = {}, bytearray()
    for name in paths:
        payload = (preview / name).read_bytes()
        files[name] = [len(data), len(payload)]
        data.extend(payload)
    packed = gzip.compress(data, compresslevel=7, mtime=0)
    archive = json.dumps({'data': base64.b64encode(packed).decode(), 'files': files}, separators=(',', ':'))
    js = (code / 'app.bundle.js').read_text(encoding='utf8').replace('</script', '<\\/script')
    html = (code / 'index.html').read_text(encoding='utf8').replace(
        '<script src="app.bundle.js"></script>',
        '<script>window.__CHARACTER_ARCHIVE=' + archive + ';</script><script>' + js + '</script>')
    output = options.out or (root / '原版人物渲染预览.html')
    output.write_text(html, encoding='utf8')
    manifest = {
        'file': output.name, 'bytes': output.stat().st_size,
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'nativeAssetBytes': len(data), 'compressedAssetBytes': len(packed),
        'files': files, 'networkRequired': False,
    }
    (root / 'preview-build.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
