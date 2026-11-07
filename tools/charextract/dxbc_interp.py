"""A small SM5 (ps_5_0) DXBC interpreter used to recover material kernel behaviour.

Adapted from the lightweight kit's `validate-body-face-port.py` interpreter and
extended with the instruction set the pet (PetBase) material family needs:
round_ne / round_ni / log / exp / dp4 / ftoi / ld_indexable / bitwise and /
immediate-constant-buffer indexing / discard_nz.

The interpreter executes the *original* cooked DXBC program, so it is the
ground truth the GLSL port is checked against. It is a material-kernel check,
not an in-game frame/render equivalence test.
"""
from __future__ import annotations

import re
import struct

import numpy as np

F32 = np.float32

# The DXBC immediate constant block of ps_5_0 shaders is always 8 float4 rows.
IMMEDIATE_CONSTANT_BLOCK = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.750000, 0.125000, 0.937500],
        [0.500000, 0.250000, 0.687500, 0.437500],
        [0.187500, 0.875000, 0.062500, 0.812500],
        [0.625000, 0.375000, 0.562500, 0.312500],
    ],
    dtype=np.float64,
)


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


def _mask_to_float(value: float) -> float:
    """0x3f800000 style masks appear as float literals in the disassembly."""
    return value


class Interpreter:
    """Executes a DXBC instruction block with numpy-vectorised lanes."""

    def __init__(self, cb, v, textures, immediate=None):
        self.cb = cb
        self.v = v
        self.r = np.zeros((16, 4), dtype=np.float64)
        self.o = np.zeros((16, 4), dtype=np.float64)
        self.int_regs = set()
        self.tex = textures
        self.immediate = IMMEDIATE_CONSTANT_BLOCK if immediate is None else immediate
        self.discarded = False

    def raw_bits(self, s, value):
        """32 bit patterns of an operand.

        A register slot is 32 bits wide whatever the instruction put there:
        an `ftoi` writes the *bit pattern* of the integer, so reading the slot
        back as a float yields the denormal `uintBitsToFloat(int)`.  Taking the
        float bits of the stored value therefore reproduces the raw slot for
        both float and integer typed registers.
        """
        arr = np.atleast_1d(np.asarray(value, dtype=np.float64))
        return arr.astype(np.float32).view(np.uint32)

    @staticmethod
    def int_value(value):
        """The signed integer held by a slot."""
        bits = np.atleast_1d(np.asarray(value, dtype=np.float64)).astype(np.float32).view(np.uint32).astype(np.int64)
        return np.where(bits >= 0x80000000, bits - 0x100000000, bits)

    @staticmethod
    def slot_from_int(values):
        """Store an integer into a slot as its 32 bit pattern."""
        bits = (np.atleast_1d(np.asarray(values, dtype=np.int64)) & 0xFFFFFFFF).astype(np.uint32)
        return bits.view(np.float32).astype(np.float64)

    def bitwise(self, z, args, kind):
        """Bitwise and/or on the 32 bit patterns.

        The disassembler renders every literal as a float, which is lossy for
        the integer masks used by the dither lookup (`and r0.yz, r0.yyzy,
        l(0, 3, 3, 0)`). Decimal literal components are therefore read as
        integer bit masks, while hexadecimal components are float bit
        patterns (`l(0x3f800000, ...)`).
        """
        if args[1].startswith('l('):
            parts = splitargs(args[1][2:-1])
            mask = []
            for part in parts:
                if part.startswith('0x'):
                    mask.append(np.uint32(int(part, 16) & 0xFFFFFFFF))
                else:
                    mask.append(np.uint32(int(float(part)) & 0xFFFFFFFF))
            mask = np.array(mask, dtype=np.uint32)
        else:
            mask = self.raw_bits(args[1], z[1])
        left = self.raw_bits(args[0], z[0])
        result = (left & mask) if kind == 'and' else (left | mask)
        return result.view(np.float32).astype(np.float64)
        result = (left & mask) if kind == 'and' else (left | mask)
        return result.view(np.float32).astype(np.float64)

    # ------------------------------------------------------------------ read
    def read_index(self, s: str) -> float:
        """Evaluate a constant-buffer index expression such as `r0.z + 4`."""
        s = s.strip()
        m = re.fullmatch(r'(.+?)\s*([+-])\s*(\d+)', s)
        if m:
            base = float(np.asarray(self.read(m.group(1).strip())).ravel()[0])
            sign = 1.0 if m.group(2) == '+' else -1.0
            return base + sign * float(m.group(3))
        return float(np.asarray(self.read(s)).ravel()[0])

    def read(self, s: str):
        neg = s.startswith('-')
        if neg:
            s = s[1:]
        absolute = s.startswith('|')
        if absolute:
            s = s.strip('|')
        if s.startswith('icb['):
            m = re.fullmatch(r'icb\[(.*?)\]\.?([xyzw]*)?', s)
            index = self.read_index(m.group(1))
            idx = int(np.clip(index, 0, len(self.immediate) - 1))
            z = np.asarray(self.immediate[idx], dtype=np.float64)
            sw = m.group(2) or 'xyzw'
            z = z[["xyzw".index(c) for c in sw]]
            if len(z) == 1:
                z = np.repeat(z, 4)
        elif s.startswith('l('):
            vals = []
            for v in splitargs(s[2:-1]):
                if v.startswith('0x') or v.startswith('0X'):
                    # Hex literals in the disassembly are 32-bit float bit patterns.
                    bits = int(v, 16)
                    vals.append(struct.unpack('<f', struct.pack('<I', bits & 0xFFFFFFFF))[0])
                else:
                    vals.append(float(v))
            if len(vals) == 1:
                z = np.repeat(np.array(vals[0]), 4)
            else:
                z = np.array(vals + [0.0] * (4 - len(vals)))
        else:
            m = re.fullmatch(r'(r\d+|v\d+|o\d+|cb\d+\[\d+\])(?:\.([xyzw]+))?', s)
            assert m, s
            base, sw = m.groups()
            sw = sw or 'xyzw'
            if base[0] == 'o':
                z = self.o[int(base[1:])]
            elif base[0] == 'r':
                z = self.r[int(base[1:])]
            elif base[0] == 'v':
                z = np.asarray(self.v[int(base[1:])], dtype=np.float64)
            else:
                bi, ri = map(int, re.findall(r'\d+', base))
                z = np.asarray(self.cb[bi][ri], dtype=np.float64)
            z = z[["xyzw".index(c) for c in sw]]
            if len(z) == 1:
                z = np.repeat(z, 4)
        if absolute:
            z = abs(z)
        return -z if neg else z

    def put(self, d: str, x, integer: bool = False):
        m = re.fullmatch(r'([ro](\d+))(?:\.([xyzw]+))?', d)
        assert m, d
        kind = m.group(1)
        ri = int(m.group(2))
        sw = m.group(3) or 'xyzw'
        if np.isscalar(x):
            x = np.full(4, float(x))
        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 0:
            x = np.full(4, float(x))
        target = self.r if kind[0] == 'r' else self.o
        for c in sw:
            index = "xyzw".index(c)
            # A source swizzle selects one source component per *position*;
            # the destination write mask then picks the positions written.
            target[ri, index] = x[min(index, np.size(x) - 1)] if np.size(x) >= 4 else x[0]
            if integer and kind[0] == 'r':
                self.int_regs.add((ri, index))
            elif kind[0] == 'r':
                self.int_regs.discard((ri, index))

    # ------------------------------------------------------------------- run
    def run(self, lines):
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            s = line.strip()
            if not s or s.startswith('//') or s.startswith('dcl_') or s.startswith('ret'):
                continue
            if s.startswith('ps_') or s.startswith('vs_'):
                continue
            if s.startswith('endif'):
                continue
            if s.startswith('if_nz') or s.startswith('if_c'):
                condition = self.read(splitargs(s.partition(' ')[2])[0])
                taken = bool(np.any(np.abs(condition) > 0))
                # find the matching endif, honouring nesting, and split the
                # then/else halves: the else body runs when the test fails.
                depth = 1
                then_body = []
                else_body = []
                current = then_body
                while index < len(lines):
                    inner = lines[index].strip()
                    index += 1
                    if inner.startswith('if_nz') or inner.startswith('if_c'):
                        depth += 1
                    elif inner.startswith('endif'):
                        depth -= 1
                        if depth == 0:
                            break
                    elif inner.startswith('else') and depth == 1:
                        current = else_body
                        continue
                    current.append(lines[index - 1])
                self.run(then_body if taken else else_body)
                continue
            op, _, rest = s.partition(' ')
            args = splitargs(rest)
            d = args[0]
            a = args[1:]
            saturate = op.endswith('_sat')
            op = op[:-4] if saturate else op

            if op.startswith('sample'):
                tex = a[1]
                m = re.match(r't(\d+)\.([xyzw]+)', tex)
                value = self.tex[int(m.group(1))]
                coords = self.read(a[0])
                if callable(value):
                    value = value(coords)
                value = np.asarray(value, dtype=np.float64)
                x = value[["xyzw".index(c) for c in m.group(2)]]
            elif op.startswith('ld_indexable'):
                # structured buffer load: dst, index, resource
                m = re.match(r't(\d+)', a[1])
                value = self.tex[int(m.group(1))]
                buffer_index = self.read(a[0])
                if callable(value):
                    value = value(buffer_index)
                value = np.asarray(value, dtype=np.float64)
                x = value
            elif op == 'discard_nz':
                operand = a[0] if a else d
                value = self.read(operand)
                if np.any(np.abs(value) > 0):
                    self.discarded = True
                continue
            elif op == 'discard_z':
                # discard when the tested value is zero
                operand = a[0] if a else d
                value = self.read(operand)
                if np.any(np.abs(value) <= 0):
                    self.discarded = True
                continue
            else:
                z = [self.read(x) for x in a]
                if op == 'mov':
                    x = z[0]
                elif op == 'add':
                    x = z[0] + z[1]
                elif op == 'mul':
                    x = z[0] * z[1]
                elif op == 'mad':
                    x = z[0] * z[1] + z[2]
                elif op == 'div':
                    # IEEE division: x/0 gives +/-inf and 0/0 gives NaN, which
                    # the saturate modifier then clamps. Replacing the division
                    # with a zero would not match the original program.
                    with np.errstate(divide='ignore', invalid='ignore'):
                        x = z[0] / z[1]
                elif op == 'min':
                    x = np.minimum(z[0], z[1])
                elif op == 'max':
                    x = np.maximum(z[0], z[1])
                elif op == 'sqrt':
                    x = np.sqrt(np.maximum(z[0], 0.0))
                elif op == 'rsq':
                    x = 1.0 / np.sqrt(np.maximum(z[0], 1e-30))
                elif op.startswith('dp'):
                    n = int(op[-1])
                    x = np.dot(z[0][:n], z[1][:n])
                elif op == 'round_ni':
                    x = np.floor(z[0] + 0.5)
                elif op == 'round_ne':
                    r = np.round(z[0])
                    x = np.where(r != z[0], 1.0, 0.0)
                elif op == 'ge':
                    x = np.where(z[0] >= z[1], -1.0, 0.0)
                elif op == 'lt':
                    x = np.where(z[0] < z[1], -1.0, 0.0)
                elif op == 'eq':
                    x = np.where(z[0] == z[1], -1.0, 0.0)
                elif op == 'and':
                    x = self.bitwise(z, a, 'and')
                    self._integer_write = True
                elif op == 'or':
                    x = self.bitwise(z, a, 'or')
                    self._integer_write = True
                elif op == 'movc':
                    x = np.where(z[0] != 0, z[1], z[2])
                elif op == 'iadd':
                    total = (self.int_value(z[0]) + self.int_value(z[1])) & 0xFFFFFFFF
                    x = self.slot_from_int(total)
                    self._integer_write = True
                elif op == 'itof':
                    x = self.int_value(z[0]).astype(np.float64)
                elif op == 'ftoi':
                    # DXBC stores the *bit pattern* of the truncated integer,
                    # not the integer value: reading the slot as a float later
                    # has to give `uintBitsToFloat(int)`.
                    x = self.slot_from_int(np.trunc(z[0]).astype(np.int64))
                    self._integer_write = True
                elif op == 'log':
                    with np.errstate(divide='ignore', invalid='ignore'):
                        x = np.log(np.maximum(z[0], 1e-30))
                elif op == 'exp':
                    with np.errstate(over='ignore', invalid='ignore'):
                        x = np.exp(z[0])
                else:
                    raise ValueError('unsupported opcode ' + op + ' in: ' + s)

            if saturate:
                with np.errstate(invalid='ignore'):
                    x = np.clip(x, 0.0, 1.0)
                    x = np.where(np.isnan(x), 0.0, x)
            self.put(d, x, integer=getattr(self, '_integer_write', False))
            self._integer_write = False
        return self
