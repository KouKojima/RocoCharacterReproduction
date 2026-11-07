import io

p = r'D:\洛克王国\洛克王国：世界(2002304)\_nrc_work\tools\charextract\prepare_multi.py'
s = io.open(p, encoding='utf-8').read()

old_start = s.index('        # material instances + shader constant buffers')
old_end = s.index('        # animation')

new = '''        # material instances + shader constant buffers
        names = entry['materials']
        kernel = entry.get('kernel', 'npc')
        instances, buffers, defs = {}, {}, {}
        if kernel == 'npc':
            kinds = ('body', 'face', 'eyes', 'outline', 'faceOutline')
            table = KIND_TEXTURE
        else:
            kinds = ('body', 'body2', 'eyes', 'outline', 'outline2')
            table = PET_KIND_TEXTURE
        for kind in kinds:
            material = names[kind]
            chain, scalar, vector, texture = effective(materials_dir, material)
            instances[kind] = {'name': material, 'chain': chain, 'scalar': scalar, 'vector': vector,
                               'texture': {k: (v or {}).get('ObjectPath', '') for k, v in texture.items()}}
            if kernel == 'npc' and kind == 'faceOutline':
                # The face outline instance carries no BaseTex/MatID override of its
                # own, so the chain defaults apply (see the kit's outline-port.txt).
                defs[kind] = dict(FACE_OUTLINE_DEFAULT)
                defs[kind]['uHue'] = COMMON_HUE
                # The face outline still renders with the recovered outline pixel
                # program, so it needs that program's constant buffer.
                buffers[kind], prefix = pick_buffer(shaders_dir, material, 'outline')
                buffers[kind]['source'] = prefix + '-evaluated.json'
                continue
            if kernel == 'pet' and kind in ('outline', 'outline2'):
                # The pet outline instance binds TestResMaskTex01 as its MatID
                # lookup; the recovered outline program samples that texture.
                defs[kind] = dict(PET_OUTLINE_DEFAULT)
                buffers[kind], prefix = pick_buffer(shaders_dir, material, 'outline')
                buffers[kind]['source'] = prefix + '-evaluated.json'
                continue
            buffers[kind], prefix = pick_buffer(shaders_dir, material, kind)
            buffers[kind]['source'] = prefix + '-evaluated.json'
            binding = {}
            for sampler, parameter in table[kind].items():
                name = texture_name(texture.get(parameter))
                if not name:
                    raise ValueError('%s (%s) has no %s override' % (material, kind, parameter))
                binding[sampler] = name
            if kind == 'outline' and kernel == 'npc':
                binding['uHue'] = COMMON_HUE
            defs[kind] = binding

        # section -> material kind, taken from the mesh's own material slots
        section_kinds = {}
        if kernel == 'npc':
            face_slot = names['face'].rsplit('/', 1)[-1]
            eyes_slot = names['eyes'].rsplit('/', 1)[-1]
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

'''

s = s[:old_start] + new + s[old_end:]
s = s.replace("        char_id = entry['id']\n", "        char_id = entry['id']\n        kernel = entry.get('kernel', 'npc')\n")
s = s.replace("'npc': entry.get('npc', ''),", "'npc': entry.get('npc', ''), 'kernel': kernel,")
s = s.replace(
    "print('PREPARED %-12s vertexs=%-7d textures=%-3d anim=%s' % (\n            char_id, meta.get('vertexCount', 0), len(textures), has_animation))",
    "print('PREPARED %-12s kernel=%-4s vertexs=%-7d textures=%-3d anim=%s' % (\n            char_id, kernel, meta.get('vertexCount', 0), len(textures), has_animation))")
s = s.replace("'sectionKinds': section_kinds, 'hasAnimation': has_animation,",
              "'sectionKinds': section_kinds, 'hasAnimation': has_animation, 'kernel': kernel,")
io.open(p, 'w', encoding='utf-8').write(s)
print('patched ok')
