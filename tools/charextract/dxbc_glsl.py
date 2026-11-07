"""Transpile the original DXBC of a cooked BasePass pixel program into GLSL.

The generated shader is a mechanical translation of the same instruction text
that `dxbc_interp` executes, so the recovered kernel and the original program
cannot drift apart. The runtime constant buffers that the cooked material does
not carry (cb0/cb1/cb2/cb3/cb4/cb5) are emitted as individual uniforms; the
values are produced by `pet_runtime.build_runtime` and written into the
preview data by the prepare step.

Only the instruction set used by the pet fragment programs is supported.
"""
from __future__ import annotations

import re

F32_FORMAT = 'vec4(%s)'


def splitargs(s: str) -> list[str]:
    out, depth, start = [], 0, 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth == 0:
            out.append(s[start:i].strip())
            start = i + 1
    return out + [s[start:].strip()]


def parse_block(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Return the executable instructions as (opcode, operands) pairs."""
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('dcl_temps'):
            start = i + 1
            break
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip().startswith('ret'):
            end = i
            break
    out = []
    for line in lines[start:end]:
        s = line.strip()
        if not s or s.startswith('//') or s.startswith('dcl_') or s.startswith('ret'):
            continue
        if s.startswith('ps_') or s.startswith('vs_'):
            continue
        op, _, rest = s.partition(' ')
        args = splitargs(rest)
        # the sample instructions carry their shader model in the opcode
        op = op.split('(')[0]
        out.append((op, args))
    return out


class Context:
    """Maps the original registers of one program onto the preview's inputs."""

    def __init__(self, material_register, vmap, tmap, output='o0'):
        self.material_register = material_register   # 'cb6' or 'cb3'
        self.vmap = vmap                              # {'v1': 'vNormal', ...}
        self.tmap = tmap                              # {'t1': 'uBase', ...}
        self.output = output


def _literal_values(text: str) -> list[float]:
    values = []
    for part in splitargs(text[2:-1]):
        if part.startswith('0x'):
            bits = int(part, 16) & 0xFFFFFFFF
            import struct
            values.append(struct.unpack('<f', struct.pack('<I', bits))[0])
        else:
            values.append(float(part))
    return values


def _literal(text: str) -> str:
    # every DXBC literal is a four component value
    values = _literal_values(text)
    if len(values) == 1:
        return 'vec4(%r)' % values[0]
    return 'vec4(%s)' % ', '.join(repr(v) for v in values)


def _literal_uint(text: str) -> str:
    parts = splitargs(text[2:-1])
    values = []
    for part in parts:
        if part.startswith('0x'):
            values.append(int(part, 16) & 0xFFFFFFFF)
        else:
            values.append(int(float(part)) & 0xFFFFFFFF)
    if len(values) == 1:
        return 'uint(%d)' % values[0]
    return 'uvec4(%s)' % ', '.join('uint(%d)' % v for v in values)


class Transpiler:
    def __init__(self, context: Context):
        self.ctx = context
        self.used_uniforms = {}     # name -> glsl type
        self.int_regs = set()       # (reg, comp) holding integer bit patterns
        self.buffers = {}           # extra uniform names per texture slot
        self.uses_discard = False

    # ------------------------------------------------------------- operands
    def expand(self, sw: str) -> str:
        """DXBC source swizzles are always four components; a short swizzle
        repeats its first component (`r0.xyz` is `r0.xyzx`)."""
        return sw if len(sw) == 4 else sw + sw[0] * (4 - len(sw))

    def operand(self, text: str, integer=False) -> str:
        text = text.strip()
        neg = text.startswith('-')
        if neg:
            text = text[1:].strip()
        absolute = text.startswith('|')
        if absolute:
            text = text.strip('|').strip()
        if text.startswith('l('):
            value = _literal_uint(text) if integer else _literal(text)
        elif text.startswith('icb['):
            m = re.fullmatch(r'icb\[(.*?)\]\.?([xyzw]*)?', text)
            value = 'icbRows[%s]' % self.index_expr(m.group(1))
        else:
            m = re.fullmatch(r'(r\d+|v\d+|o\d+|cb\d+\[\d+\])(?:\.([xyzw]+))?', text)
            if not m:
                raise ValueError('unsupported operand ' + text)
            base, sw = m.group(1), m.group(2)
            if sw:
                sw = self.expand(sw)
            if base[0] == 'r':
                value = 'r' + base[1:] + ('.' + sw if sw else '')
            elif base[0] == 'v':
                name = self.ctx.vmap.get(base)
                if name is None:
                    raise ValueError('unmapped input register ' + base)
                value = name + ('.' + sw if sw else '')
            elif base[0] == 'o':
                if base == self.ctx.output:
                    value = 'outColor' + ('.' + sw if sw else '')
                else:
                    # the auxiliary output register is a single float
                    value = 'outAux'
            else:
                bi, ri = map(int, re.findall(r'\d+', base))
                value = self.constant(bi, ri) + ('.' + sw if sw else '')
        if absolute:
            value = 'abs(%s)' % value
        if neg:
            value = '(-%s)' % value
        return value

    def scalar_operand(self, text: str) -> str:
        """A single component of an operand, as a float."""
        text = text.strip()
        m = re.fullmatch(r'(r\d+|v\d+|cb\d+\[\d+\])(?:\.([xyzw]+))?', text)
        if m and m.group(2):
            return '%s.%s' % (self.operand(m.group(1)), m.group(2)[0])
        return '%s.x' % self.operand(text)

    def to_bits(self, expr: str) -> str:
        """The 32 bit patterns of a four component value."""
        return ('uvec4(floatBitsToUint((%s).x),floatBitsToUint((%s).y),'
                'floatBitsToUint((%s).z),floatBitsToUint((%s).w))' % (expr, expr, expr, expr))

    def from_bits(self, bits: str) -> str:
        return ('vec4(uintBitsToFloat((%s).x),uintBitsToFloat((%s).y),'
                'uintBitsToFloat((%s).z),uintBitsToFloat((%s).w))' % (bits, bits, bits, bits))

    def index_expr(self, text: str) -> str:
        text = text.strip()
        m = re.fullmatch(r'(.+?)\s*([+-])\s*(\d+)', text)
        if m:
            base = 'int(floatBitsToUint(%s))' % self.scalar_operand(m.group(1).strip())
            sign = '+' if m.group(2) == '+' else '-'
            return '(%s %s %s)' % (base, sign, m.group(3))
        return 'int(floatBitsToUint(%s))' % self.scalar_operand(text)

    def constant(self, register: int, row: int) -> str:
        if register == int(self.ctx.material_register[2:]):
            return 'uMat[%d]' % row
        name = 'uCb%d_%d' % (register, row)
        self.used_uniforms[name] = 'vec4'
        return name

    def texture(self, slot: int, swizzle: str) -> str:
        name = self.ctx.tmap.get(slot)
        if name is None:
            raise ValueError('unmapped texture slot t%d' % slot)
        return 'texture(%s, %s)' % (name, self.current_coords)

    # ------------------------------------------------------------ emission
    def emit(self, ops) -> str:
        return self.emit_range(ops, 0, len(ops))

    def emit_range(self, ops, start, end) -> str:
        out = []
        i = start
        while i < end:
            op, args = ops[i]
            if op.startswith('if_nz') or op.startswith('if_c'):
                depth = 1
                j = i + 1
                else_at = None
                while j < end:
                    inner = ops[j][0]
                    if inner.startswith('if_nz') or inner.startswith('if_c'):
                        depth += 1
                    elif inner == 'endif':
                        depth -= 1
                        if depth == 0:
                            break
                    elif inner == 'else' and depth == 1:
                        else_at = j
                    j += 1
                # a truncated probe can cut inside a branch: the body must stop
                # at the cut, otherwise the probe would run past the instruction
                # it is meant to stop at.
                then_end = min(else_at if else_at is not None else j, end)
                then_body = self.emit_range(ops, i + 1, then_end)
                condition = self.operand(args[0])
                if else_at is not None and else_at < end:
                    else_body = self.emit_range(ops, else_at + 1, min(j, end))
                    out.append('if (any(greaterThan(abs(%s), vec4(0.0)))) {\n%s\n} else {\n%s\n}'
                               % (condition, then_body, else_body))
                else:
                    out.append('if (any(greaterThan(abs(%s), vec4(0.0)))) {\n%s\n}' % (condition, then_body))
                i = j + 1
                continue
            if op in ('else', 'endif'):
                i += 1
                continue
            out.append(self.emit_one(op, args))
            i += 1
        return '\n'.join(out)

    def emit_one(self, op: str, args: list[str]) -> str:
        modifier = ''
        base = op
        if base.endswith('_sat'):
            base = base[:-4]
            modifier = 'sat'
        if base.startswith('sample'):
            return self.emit_sample(base, args)
        if base == 'discard_nz':
            self.uses_discard = True
            return 'if (any(greaterThan(abs(%s), vec4(0.0)))) discard;' % self.operand(args[0])
        if base == 'discard_z':
            self.uses_discard = True
            text = args[0]
            m = re.fullmatch(r'[ro]\d+\.([xyzw])', text)
            if m:
                return 'if (%s == 0.0) discard;' % self.scalar_operand(text)
            return 'if (any(equal(%s, vec4(0.0)))) discard;' % self.operand(text)
        if base == 'ld_indexable':
            # The shadow ramp lookup buffer (t0) is a structured buffer the
            # cooked asset does not carry; the preview supplies the value as a
            # vec4 uniform, matching the interpreter's buffer stand-in.
            name = 'uShadowLut'
            self.used_uniforms[name] = 'vec4'
            dst = args[0]
            return self.assign(dst, name)
        if base in ('if_nz', 'if_c'):
            return 'if (any(greaterThan(abs(%s), vec4(0.0)))) {' % self.operand(args[0])
        if base == 'endif':
            return '}'

        dst = args[0]
        src = [self.operand(a) for a in args[1:]]
        if base == 'mov':
            value = src[0]
        elif base == 'add':
            value = '(%s + %s)' % (src[0], src[1])
        elif base == 'mul':
            value = '(%s * %s)' % (src[0], src[1])
        elif base == 'mad':
            value = '(%s * %s + %s)' % (src[0], src[1], src[2])
        elif base == 'div':
            value = '(%s / %s)' % (src[0], src[1])
        elif base == 'min':
            value = 'min(%s, %s)' % (src[0], src[1])
        elif base == 'max':
            value = 'max(%s, %s)' % (src[0], src[1])
        elif base == 'sqrt':
            value = 'sqrt(max(%s, vec4(0.0)))' % src[0]
        elif base == 'rsq':
            value = '(1.0 / sqrt(max(%s, vec4(1e-30))))' % src[0]
        elif base == 'dp3':
            value = 'vec4(dot(%s.xyz, %s.xyz))' % (src[0], src[1])
        elif base == 'dp4':
            value = 'vec4(dot(%s, %s))' % (src[0], src[1])
        elif base == 'round_ni':
            value = 'floor(%s + 0.5)' % src[0]
        elif base == 'round_ne':
            # 1.0 when the rounded value differs, 0.0 otherwise.  The select is
            # written as `1 - flag` instead of `mix()`: this ANGLE build folds
            # `mix()` over a boolean derived vector incorrectly.
            value = 'vec4(1.0) - vec4(equal(round(%s), %s))' % (src[0], src[0])
        elif base == 'ge':
            value = 'vec4(0.0) - vec4(greaterThanEqual(%s, %s))' % (src[0], src[1])
        elif base == 'lt':
            value = 'vec4(0.0) - vec4(lessThan(%s, %s))' % (src[0], src[1])
        elif base == 'eq':
            value = 'vec4(0.0) - vec4(equal(%s, %s))' % (src[0], src[1])
        elif base in ('and', 'or'):
            op_sym = '&' if base == 'and' else '|'
            left = args[1]
            right = args[2]
            left_expr = self.operand(left, integer=True) if left.startswith('l(') else self.to_bits(self.operand(left))
            right_expr = self.operand(right, integer=True) if right.startswith('l(') else self.to_bits(self.operand(right))
            value = self.from_bits('(%s %s %s)' % (left_expr, op_sym, right_expr))
            self.mark_integer(dst)
            return self.assign(dst, value)
        elif base == 'movc':
            # dst = cond ? a : b, written as b + (a - b) * flag because this
            # ANGLE build folds `mix()` over a boolean derived vector wrongly.
            value = ('(%s + (%s - %s) * vec4(notEqual(%s, vec4(0.0))))'
                     % (src[2], src[1], src[2], src[0]))
        elif base == 'ftoi':
            value = self.from_bits('uvec4(ivec4(trunc(%s)))' % src[0])
            self.mark_integer(dst)
            return self.assign(dst, value)
        elif base == 'log':
            value = 'log(max(%s, vec4(1e-30)))' % src[0]
        elif base == 'exp':
            value = 'exp(%s)' % src[0]
        else:
            raise ValueError('unsupported opcode ' + op)

        if modifier == 'sat':
            value = 'clamp(%s, 0.0, 1.0)' % value
        return self.assign(dst, value)

    def mark_integer(self, dst: str) -> None:
        m = re.fullmatch(r'r(\d+)(?:\.([xyzw]+))?', dst)
        if not m:
            return
        ri = int(m.group(1))
        for c in (m.group(2) or 'xyzw'):
            self.int_regs.add((ri, 'xyzw'.index(c)))

    def assign(self, dst: str, value: str) -> str:
        m = re.fullmatch(r'([ro])(\d+)(?:\.([xyzw]+))?', dst)
        if not m:
            raise ValueError('unsupported destination ' + dst)
        kind, ri, sw = m.group(1), m.group(2), m.group(3) or 'xyzw'
        if kind == 'r':
            target = 'r' + ri
        elif ri == self.ctx.output[1:]:
            target = 'outColor'
        else:
            # the auxiliary output register is a single float
            return 'outAux = (%s).%s;' % (value, sw[0])
        if sw == 'xyzw':
            return '%s = (%s);' % (target, value)
        return '%s.%s = (%s).%s;' % (target, sw, value, sw)

    def emit_sample(self, base: str, args: list[str]) -> str:
        m = re.match(r't(\d+)\.([xyzw]+)', args[2])
        slot = int(m.group(1))
        swizzle = m.group(2)
        coords = self.operand(args[1])
        name = self.ctx.tmap.get(slot)
        if name is None:
            raise ValueError('unmapped texture slot t%d' % slot)
        if base.startswith('sample_l'):
            coords = '(%s)' % coords
        value = 'texture(%s, (%s).xy)' % (name, coords)
        if swizzle == 'xyzw':
            return self.assign(args[0], value)
        # the destination swizzle selects the source components
        return self.assign(args[0], '(%s).%s' % (value, swizzle))
