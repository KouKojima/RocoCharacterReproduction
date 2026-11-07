"""Assemble a multi-character preview from per-character extraction folders.

Local helper (not part of the handoff bundle). Everything it consumes was
produced by the kit's own probes or by the parameterized NrcChar probe; this
script only re-assembles that data into the per-character asset layout the
preview expects, deriving texture bindings from the material instances instead
of hard-coding sample names.
"""
from pathlib import Path
import argparse, json, hashlib, shutil
from PIL import Image

# TMobileBasePassPS FNoLightMapPolicy0 + HDRLinear64 + Skylight + DEFAULT_UE_CSM
BASE_PASS_PS_TYPE = '7314494563231833460'
# Pixel programs the recovered GLSL ports were derived from.
REFERENCE_PS = {
    'body': 'fb556f9017a383e6e995014526b91d2a681ec9b2',
    # The second body slot runs the same object pixel program as the body.
    'im': 'fb556f9017a383e6e995014526b91d2a681ec9b2',
    'face': 'fca52541baeaff6914775dbf81e98de3eaaa1640',
    'eyes': 'dd80d2e26f07129b97cc1c093eae479f6fb10960',
    'outline': '758ab8acf6923046b9527339276a97204982a366',
}
# Material instance texture parameter -> shader sampler.
KIND_TEXTURE = {
    'body': {'uBase': 'BaseTex', 'uMask': 'MaskTex', 'uId': 'MatID', 'uMatcap': 'MatCap'},
    # A second body section drawn with the same object material graph but its
    # own instance (the NPC_*_Im slot). It runs the body pixel program.
    'im': {'uBase': 'BaseTex', 'uMask': 'MaskTex', 'uId': 'MatID', 'uMatcap': 'MatCap'},
    'face': {'uBase': 'BaseTex', 'uMask': 'MaskTex', 'uId': 'MatID', 'uFace': 'FaceTex'},
    'eyes': {'uBase': 'PupilTex'},
    'outline': {'uBase': 'BaseTex', 'uId': 'MatID'},
}
# The pet family (PetBase) uses its own parameter names: EyeTex for the eye
# texture and MatID/MainTex for the outline lookup.
PET_KIND_TEXTURE = {
    'body': {'uBase': 'BaseTex', 'uMask': 'MaskTex'},
    'body2': {'uBase': 'BaseTex', 'uMask': 'MaskTex'},
    'eyes': {'uBase': 'EyeTex'},
    'outline': {'uId': 'MatID'},
    'outline2': {'uId': 'MatID'},
}
# The pet body shader samples a ramp texture from slot 5. The pet material
# chain does not override it, so the M_P_Object default applies:
# NRC/Content/ArtRes/AnimSequence/Human/CommonTex/CommonRampTex/T_AllDebugRamp.
PET_DEFAULT_TEXTURE = {'uRamp': 'T_AllDebugRamp'}
# MI_NPC_Fe_01_Outline carries no BaseTex/MatID override; the chain defaults
# are TestResMainTex01 / TestResIDTex (see the kit's outline-port.txt).
FACE_OUTLINE_DEFAULT = {'uBase': 'TestResMainTex01', 'uId': 'TestResIDTex'}
COMMON_HUE = 'T_Outline_Hue'
# The pet outline samples its MatID lookup; the instance binds TestResMaskTex01.
PET_OUTLINE_DEFAULT = {'uId': 'TestResMaskTex01'}


def load_material(materials_dir, name):
    path = materials_dir / (name + '.json')
    if not path.exists():
        raise FileNotFoundError('missing material export ' + str(path))
    data = json.loads(path.read_text(encoding='utf8'))
    return data[0] if isinstance(data, list) else data


def material_chain(materials_dir, name):
    chain, current, seen = [], name, set()
    while current and current not in seen:
        seen.add(current)
        path = materials_dir / (current + '.json')
        if not path.exists():
            break
        obj = load_material(materials_dir, current)
        if not isinstance(obj, dict):
            break
        chain.append(obj)
        parent = obj.get('Properties', {}).get('Parent', {}).get('ObjectPath')
        current = parent.rsplit('/', 1)[-1].split('.')[0] if parent else None
    return chain


def effective(materials_dir, name):
    """Resolve scalar/vector/texture parameters through the parent chain.

    Ancestors first, descendants last: a descendant overrides the ancestor.

    The pet material family also carries layered (BlendParameter) overrides.
    A layered entry is the value of the same parameter for one material layer;
    the cooked asset used by the runtime always resolves layer 0 for these
    instances, so layer 0 is used and the remaining layers are reported
    separately instead of being silently dropped.
    """
    chain = material_chain(materials_dir, name)
    scalar, vector, texture = {}, {}, {}
    layered = []
    for level in reversed(chain):
        props = level.get('Properties', {})
        for field, target in (('ScalarParameterValues', scalar),
                              ('VectorParameterValues', vector),
                              ('TextureParameterValues', texture)):
            local = {}
            for entry in props.get(field, []):
                info = entry['ParameterInfo']
                association = str(info['Association'])
                index = info['Index']
                if association == 'BlendParameter':
                    if index not in (0, -1):
                        layered.append({'material': name, 'parameter': info['Name'], 'layer': index})
                        continue
                elif association not in ('GlobalParameter', '0') or index not in (-1, 0):
                    raise ValueError('layered parameter needs an explicit adapter: ' + str(info))
                local.setdefault(info['Name'], entry['ParameterValue'])
            target.update(local)
    names = [level.get('Name') for level in chain]
    return names, scalar, vector, texture, layered


def texture_name(value):
    path = (value or {}).get('ObjectPath', '')
    return path.rsplit('/', 1)[-1].split('.')[0] if path else None


def material_default_textures(materials_dir, name):
    """Read the texture parameters the material graph itself binds.

    A material instance only stores the parameters it overrides; the rest stay
    at the value the graph's own `CachedExpressionData` holds. When an instance
    has no override for a sampler (for example the face material of an NPC
    whose face slot has no mask texture), the graph default is what the game
    samples, so it is used instead of failing the build.

    The default lives on the base material of the chain (M_C_Face for the face
    graph, M_C_Object for the body graph), so the whole chain is walked.
    """
    defaults = {}
    for level in reversed(material_chain(materials_dir, name)):
        parameters = (level.get('CachedExpressionData') or {}).get('Parameters') or {}
        entries = parameters.get('RuntimeEntries[2]', {}).get('ParameterInfos', [])
        values = parameters.get('TextureValues') or []
        for index, value in enumerate(values):
            if index >= len(entries):
                break
            parameter = entries[index].get('Name')
            texture = texture_name(value)
            if parameter and texture:
                defaults.setdefault(parameter, texture)
    return defaults


def pick_buffer(shaders_dir, material, kind):
    """Select the saved resource variant whose BasePass pixel program is the
    one the recovered port was derived from."""
    inventory = json.loads((shaders_dir / 'inventory.json').read_text(encoding='utf8'))
    wanted = REFERENCE_PS.get(kind)
    prefixes = []
    for record in inventory:
        if record['name'] != material or record['frequency'] != 'SF_Pixel':
            continue
        if str(record['type']) != BASE_PASS_PS_TYPE:
            continue
        if wanted is not None and record['shaderHash'] == wanted:
            prefixes.append(record['prefix'])
    if not prefixes:
        raise ValueError('no saved resource of %s uses the referenced BasePass program %s' % (material, wanted[:16] if wanted else kind))
    prefix = sorted(prefixes)[0]
    matches = sorted(shaders_dir.glob(prefix + '-evaluated.json'))
    if len(matches) != 1:
        raise ValueError('expected one evaluated constant buffer for ' + prefix)
    return json.loads(matches[0].read_text(encoding='utf8')), prefix


def pick_buffer_self(shaders_dir, material, materials_dir=None):
    """Select a material's own first BasePass resource.

    The pet family is a different material graph from the humanoid one, so its
    BasePass programs are not the ones the recovered humanoid port was derived
    from. For those materials the runtime variant is the first BasePass entry
    of the instance's own LoadedMaterialResources list, i.e. the first
    BasePass record the instance declares. The choice is recorded in the
    generated materials.json so it stays auditable.
    """
    inventory = json.loads((shaders_dir / 'inventory.json').read_text(encoding='utf8'))
    candidates = [r for r in inventory
                  if r['name'] == material and r['frequency'] == 'SF_Pixel'
                  and str(r['type']) == BASE_PASS_PS_TYPE]
    if not candidates:
        raise ValueError('no BasePass resource for ' + material)
    # The instance declares its resources in order; the first declared one is
    # the default BasePass variant. Order the records by that declaration.
    order = {}
    try:
        source_dir = materials_dir if materials_dir else shaders_dir.parent
        material_json = json.loads((source_dir / (material + '.json')).read_text(encoding='utf8'))
        material_json = material_json[0] if isinstance(material_json, list) else material_json
        for index, resource in enumerate(material_json.get('LoadedMaterialResources', [])):
            order[resource['LoadedShaderMap']['ResourceHash']] = index
    except (OSError, KeyError, ValueError):
        order = {}
    candidates.sort(key=lambda r: (order.get(r['resourceHash'], 1 << 30), r['instructions']))
    prefix = candidates[0]['prefix']
    matches = sorted(shaders_dir.glob(prefix + '-evaluated.json'))
    if len(matches) != 1:
        raise ValueError('expected one evaluated constant buffer for ' + prefix)
    return json.loads(matches[0].read_text(encoding='utf8')), prefix


def build_textures(source_dir, out_dir):
    manifest = json.loads((source_dir / 'manifest.json').read_text(encoding='utf8'))
    textures, total = [], 0
    for entry in manifest:
        mips, data = [], bytearray()
        for mip in entry['mips']:
            image = Image.open(source_dir / mip['file']).convert('RGBA')
            width, height = mip['logicalWidth'], mip['logicalHeight']
            if not (image.width >= width and image.height >= height):
                raise ValueError('mip smaller than logical size: ' + entry['name'])
            image = image.crop((0, 0, width, height))
            payload = image.tobytes()
            mips.append({'width': width, 'height': height, 'offset': len(data), 'length': len(payload)})
            data.extend(payload)
        file = entry['name'] + '.rgba'
        (out_dir / file).write_bytes(data)
        total += len(data)
        textures.append({k: entry[k] for k in ('name', 'path', 'srgb', 'format', 'width', 'height')}
                        | {'file': file, 'sha256': hashlib.sha256(data).hexdigest(), 'mips': mips})
    (out_dir / 'textures.json').write_text(json.dumps(textures, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    return textures, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='multi-character workspace root')
    parser.add_argument('--materials', type=Path, default=None, help='folder with exported material json')
    parser.add_argument('--shaders', type=Path, default=None, help='folder with extracted shader resources')
    parser.add_argument('--manifest', type=Path, required=True, help='character manifest json')
    parser.add_argument('--out', type=Path, required=True, help='preview output root')
    options = parser.parse_args()
    root = options.data.resolve()
    materials_dir = (options.materials or (root / 'materials')).resolve()
    shaders_dir = (options.shaders or (root / 'shaders')).resolve()
    manifest = json.loads(options.manifest.read_text(encoding='utf8'))
    assets_root = options.out / 'preview' / 'assets'
    assets_root.mkdir(parents=True, exist_ok=True)

    characters = []
    for entry in manifest['characters']:
        char_id = entry['id']
        kernel = entry.get('kernel', 'npc')
        # A character may live in its own material/shader folder (the pet
        # family uses the PetBase material chain, which is a different graph).
        char_materials = Path(entry['materialsDir']).resolve() if entry.get('materialsDir') else materials_dir
        char_shaders = Path(entry['shadersDir']).resolve() if entry.get('shadersDir') else shaders_dir
        source = root / 'chars' / char_id
        out_dir = assets_root / entry['dir']
        out_dir.mkdir(parents=True, exist_ok=True)

        # model
        shutil.copy2(source / 'preview' / 'assets' / 'character.bin', out_dir / 'character.bin')
        meta = json.loads((source / 'preview' / 'assets' / 'character.json').read_text(encoding='utf8'))
        meta['sha256'] = hashlib.sha256((out_dir / 'character.bin').read_bytes()).hexdigest()
        (out_dir / 'character.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf8')

        # textures
        textures, texture_bytes = build_textures(source / 'preview-native-textures', out_dir)

        # material instances + shader constant buffers
        names = entry['materials']
        kernel = entry.get('kernel', 'npc')
        instances, buffers, defs = {}, {}, {}
        if kernel == 'npc':
            kinds = ['body', 'face', 'eyes', 'outline', 'faceOutline']
            table = KIND_TEXTURE
        else:
            kinds = ['body', 'body2', 'eyes', 'outline', 'outline2']
            table = PET_KIND_TEXTURE
        # An NPC can own a second body slot (MI_NPC_XXXXXX_Im) that runs the
        # same object pixel program with its own textures and constant buffer.
        if kernel == 'npc' and names.get('im'):
            kinds.insert(1, 'im')
        for kind in kinds:
            material = names[kind]
            chain, scalar, vector, texture, layered = effective(char_materials, material)
            instances[kind] = {'name': material, 'chain': chain, 'scalar': scalar, 'vector': vector,
                               'texture': {k: (v or {}).get('ObjectPath', '') for k, v in texture.items()}}
            if layered:
                instances[kind]['unusedLayers'] = layered
            if kernel == 'npc' and kind == 'faceOutline':
                # The face outline instance carries no BaseTex/MatID override of its
                # own, so the chain defaults apply (see the kit's outline-port.txt).
                defs[kind] = dict(FACE_OUTLINE_DEFAULT)
                defs[kind]['uHue'] = COMMON_HUE
                # The face outline still renders with the recovered outline pixel
                # program, so it needs that program's constant buffer.
                buffers[kind], prefix = pick_buffer(char_shaders, material, 'outline')
                buffers[kind]['source'] = prefix + '-evaluated.json'
                continue
            if kernel == 'pet' and kind in ('outline', 'outline2'):
                # The pet outline instance binds TestResMaskTex01 as its MatID
                # lookup; the recovered outline program samples that texture.
                defs[kind] = dict(PET_OUTLINE_DEFAULT)
                buffers[kind], prefix = pick_buffer_self(char_shaders, material, char_materials)
                buffers[kind]['source'] = prefix + '-evaluated.json'
                continue
            if kernel == 'pet':
                buffers[kind], prefix = pick_buffer_self(char_shaders, material, char_materials)
                buffers[kind]['source'] = prefix + '-evaluated.json'
            else:
                buffers[kind], prefix = pick_buffer(char_shaders, material, kind)
                buffers[kind]['source'] = prefix + '-evaluated.json'
            binding = {}
            defaults_used = {}
            for sampler, parameter in table[kind].items():
                name = texture_name(texture.get(parameter))
                if not name:
                    # The instance does not override this slot; the graph's own
                    # default texture is what the game samples.
                    name = material_default_textures(char_materials, material).get(parameter)
                    if name:
                        defaults_used[parameter] = name
                if not name:
                    raise ValueError('%s (%s) has no %s override' % (material, kind, parameter))
                binding[sampler] = name
            if defaults_used:
                instances[kind]['graphDefaultTextures'] = defaults_used
            if kernel == 'pet':
                # Sampler slots the material chain leaves at the graph default
                # still need a texture bound; the defaults come from the base
                # material's own texture slots.
                for sampler, default_name in PET_DEFAULT_TEXTURE.items():
                    binding.setdefault(sampler, default_name)
            if kind == 'outline' and kernel == 'npc':
                binding['uHue'] = COMMON_HUE
            defs[kind] = binding

        # section -> material kind, taken from the mesh's own material slots
        section_kinds = {}
        if kernel == 'npc':
            face_slot = names['face'].rsplit('/', 1)[-1]
            eyes_slot = names['eyes'].rsplit('/', 1)[-1]
            im_slot = names['im'].rsplit('/', 1)[-1] if names.get('im') else None
            for section in meta.get('sections', []):
                material = section.get('meshMaterial') or {}
                if isinstance(material, str):
                    label = material
                else:
                    label = material.get('path') or material.get('MaterialSlotName') or ''
                if face_slot in label:
                    kind = 'face'
                elif eyes_slot in label:
                    kind = 'eyes'
                elif im_slot and im_slot in label:
                    kind = 'im'
                else:
                    kind = 'body'
                section_kinds[str(section['section'])] = kind
        else:
            # The pet mesh has a body part, a body overlay and the eyes; the slot
            # names come from the mesh itself, so the mapping is derived from the
            # material instance names rather than assumed.
            body_slot = names['body'].rsplit('/', 1)[-1]
            body2_slot = names['body2'].rsplit('/', 1)[-1]
            eyes_slot = names['eyes'].rsplit('/', 1)[-1]
            for section in meta.get('sections', []):
                material = section.get('meshMaterial') or {}
                if isinstance(material, str):
                    label = material
                else:
                    label = material.get('path') or material.get('MaterialSlotName') or ''
                if eyes_slot in label:
                    kind = 'eyes'
                elif body2_slot in label:
                    kind = 'body2'
                else:
                    kind = 'body'
                section_kinds[str(section['section'])] = kind

        # animation
        animation_source = None
        for candidate in (source / 'animation', source / 'preview' / 'assets' / 'animation'):
            if (candidate / 'manifest.json').exists():
                animation_source = candidate
                break
        animation_dir = out_dir / 'animation'
        has_animation = animation_source is not None
        if has_animation:
            if animation_dir.exists():
                shutil.rmtree(animation_dir)
            shutil.copytree(animation_source, animation_dir)

        (out_dir / 'materials.json').write_text(json.dumps({
            'instances': instances, 'buffers': buffers, 'defs': defs,
            'sectionKinds': section_kinds, 'hasAnimation': has_animation, 'kernel': kernel,
        }, ensure_ascii=False, separators=(',', ':')), encoding='utf8')

        characters.append({
            'id': char_id, 'dir': entry['dir'], 'label': entry.get('label', char_id),
            'npc': entry.get('npc', ''), 'kernel': kernel,
            'stats': '%s / %d 顶点 / %d 三角面' % (entry.get('npc', char_id),
                                                 meta.get('vertexCount', 0),
                                                 meta.get('indexCount', 0) // 3),
            'textures': len(textures), 'textureBytes': texture_bytes, 'hasAnimation': has_animation,
        })
        print('PREPARED %-12s kernel=%-4s vertexs=%-7d textures=%-3d anim=%s' % (
            char_id, kernel, meta.get('vertexCount', 0), len(textures), has_animation))

    (assets_root / 'characters.json').write_text(json.dumps(characters, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    print('PREPARED %d characters' % len(characters))


if __name__ == '__main__':
    main()
