"""Run the full character extraction chain for one character.

Local helper (not part of the handoff bundle). Mirrors the kit's
character/run_character.py sequence, but with the sample character replaced by
a parameter and the two sample-locked kit steps (export_facial_poses.py,
compact_facial_data.py) reused unchanged.
"""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys

WORKSPACE = Path(__file__).resolve().parents[2]
KIT = WORKSPACE / '_unpack_guide' / 'nrc-lightweight-kit'


def run(argv, cwd=None, quiet=False):
    argv = [str(x) for x in argv]
    print('RUN', subprocess.list2cmdline(argv), flush=True)
    result = subprocess.run(argv, cwd=cwd, capture_output=quiet, text=True)
    if result.returncode != 0:
        if quiet and result.stdout:
            print(result.stdout[-4000:])
        if result.stderr:
            print(result.stderr[-4000:])
        raise SystemExit('step failed: ' + subprocess.list2cmdline(argv))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paks', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='character extraction root')
    parser.add_argument('--npc', required=True, help='asset id, e.g. NPC_01101')
    parser.add_argument('--mesh', default=None)
    parser.add_argument('--root', default=None)
    parser.add_argument('--textures', default='', help='semicolon separated texture asset names')
    parser.add_argument('--clips', default='', help='comma separated clip names')
    parser.add_argument('--key', type=Path, default=None)
    parser.add_argument('--skip-extract', action='store_true', help='reuse an existing export')
    options = parser.parse_args()
    out = options.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    key = options.key or (KIT / 'secrets' / 'base-key.bin')
    probe = WORKSPACE / 'tools' / 'NrcChar' / 'NrcChar.csproj'

    if not options.skip_extract:
        argv = ['dotnet', 'run', '--no-build', '--project', probe, '--',
                '--paks', options.paks, '--out', out, '--npc', options.npc, '--key', key]
        if options.mesh:
            argv += ['--mesh', options.mesh]
        if options.root:
            argv += ['--root', options.root]
        if options.textures:
            argv += ['--textures', options.textures]
        if options.clips:
            argv += ['--clips', options.clips]
        argv += ['model', 'textures', 'anim', 'poses', 'dialogue']
        run(argv)

    # kit steps, reused unchanged
    run([sys.executable, KIT / 'character' / 'animation-research' / 'morph-poses' / 'export_facial_poses.py', '--data', out])
    run([sys.executable, KIT / 'character' / 'animation-research' / 'facial-runtime' / 'compact_facial_data.py', '--data', out])

    # animation folder for the preview
    run([sys.executable, WORKSPACE / 'tools' / 'charextract' / 'prepare_anim.py', '--data', out])

    # kit animation validator, placed beside the data it checks
    native = out / 'animation-research' / 'native-animation'
    shutil.copy2(KIT / 'character' / 'animation-research' / 'native-animation' / 'validate_animation_exports.py', native / 'validate_animation_exports.py')
    run([sys.executable, native / 'validate_animation_exports.py'])

    print('READY ' + str(out))


if __name__ == '__main__':
    main()
