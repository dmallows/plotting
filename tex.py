import os
import time
import threading
import subprocess as sp
import operator
import itertools
import re
from functools import partial
from contextlib import contextmanager
import tempfile
import shutil

try:
    import Queue as queue
except ImportError:
    import queue

DVI2TP = 2**-16
TP2PT = 72.00 / 72.27
DVI2PT = DVI2TP * TP2PT

def read_bytes(stream, n, islice=itertools.islice):
    """
    Read the given number of bytes from given byte iterator

   """
    return bytearray(islice(stream, n))


def read_string(stream, n,
                imap=itertools.imap, islice=itertools.islice):
    """
    Read the given number of chars from given byte iterator

    """
    return ''.join(imap(chr, islice(stream, n)))


def read_array(stream, typ, n):
    return [typ(stream) for _ in xrange(n)]


def fmt(*fields):
    """
    Combine parsers together, returning a composite parser which applies each in
    sequence and returns a tuple of their results.

    """
    names = [i.__name__ for i in fields]
    keywords = (', '.join('%s=%s' % (i,i) for i in set(names)))

    func = 'def fmt(stream, %s):\n' % keywords
    ind = '    '
    func += ind + 'return (\n'
    func += ',\n'.join(ind * 2 + i + "(stream)" for i in names)
    func += '\n' + 2*ind + ')'

    ns = dict(zip(names, fields))
    exec compile(func, '<string>', 'exec') in ns
    return ns['fmt']

###########################################
# These were unrolled and manually tidied #
###########################################

def I1(stream):
    total = next(stream)
    return total


def I2(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    return total


def I3(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    return total


def I4(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    return total


def i1(stream):
    total = next(stream)
    # Convert to signed
    if total >= 128:
        total -= 256
    return total


def i2(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    # Convert to signed
    if total >= 32768:
        total -= 65536
    return total


def i3(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    # Convert to signed
    if total >= 8388608:
        total -= 16777216
    return total


def i4(stream):
    total = next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    total *= 256
    total += next(stream)
    # Convert to signed
    if total >= 2147483648:
        total -= 4294967296
    return total


# Want an array of these
unsigned = None, I1, I2, I3, I4
signed = None, i1, i2, i3, i4


# Kpsewhich is the standard unixy way of finding TeX files. Unfortunately, the
# TeX distros on a certain outdated run target (SLC5) does not come with the
# kpsewhich library. So we have to make do with the program
def kpsewhich(fname):
    """Run kpsewhich with the necessary arguments"""
    query = 'kpsewhich', fname
    return sp.Popen(query, stdout=sp.PIPE).communicate()[0].strip()


# Fontmap handles loading of fontmap, and determines encodings and files to use
class FontMap(object):
    """Handles TeX's fontmaps"""
    def __init__(self, fontmap='psfonts.map'):
        fontmap = open(kpsewhich(fontmap))
        try:
            mapping = []
            for a, b in (line.split(' ', 1) for line in fontmap):
                mapping.append((a, b))
                if a.endswith('--base'):
                    mapping.append((a[:-6], b))

            self._mapping = dict(mapping)
        finally:
            fontmap.close()

        self._encodings = {}
        self._pfbs = {}

    def get(self, fontname):
        line = self._mapping.get(fontname)

        if not line:
            return None

        in_quote = False
        names = []
        psopts = []
        pfbs = []
        encodings = []

        for token in line.split():
            if in_quote:
                if token == '"':
                    in_quote = False
                else:
                    psopts.append(token)
            else:
                if token == '"':
                    in_quote = True
                elif token.startswith('<<'):
                    pfbs.append(token[2:])
                elif token.startswith('<['):
                    encodings.append(token[2:])
                elif token.startswith('<'):
                    r = token[1:]
                    if r.endswith('.enc'):
                        encodings.append(r)
                    elif r.endswith('.pfb') or r.endswith('.pfa'):
                        pfbs.append(token[1:])
                else:
                    names.append(token)

        def read_encoding(enc):
            # TODO: HACK HACK HACK HACK HACK!
            vec = []
            with open(kpsewhich(enc), 'r') as encfile:
                lines = [line.split('%', 1)[0].strip() for line in encfile]
                lines = [line.split() for line in lines if line]

                for words in lines[1:-1]:
                    vec.extend(w.lstrip('/') for w in words)

            return vec

        if not encodings:
            encodings = ['dvips.enc']

        all_encs = self._encodings

        new_encodings = frozenset(encodings).difference(self._encodings)
        self._encodings.update(zip(new_encodings, map(read_encoding, new_encodings)))

        encodings = [(e, all_encs[e]) for e in encodings]

        self._pfbs.update((i, kpsewhich(i)) for i in frozenset(pfbs).difference(self._pfbs))

        pfbs = [self._pfbs[i] for i in pfbs]

        return names, pfbs, encodings, psopts


fontmap = FontMap()

# This is almost certainly a bottleneck, but wait for the profiler
def tfm_widths(stream, n, z, read_bytes=read_bytes):
    """
    Read in the widths from the TFM file, converting using the scaling factor
    given in the DVI file

    """
    alpha = 16
    while z >= 0o40000000:
        z //= 2
        alpha += alpha

    beta = 256 // alpha
    alpha *= z

    bytes = (read_bytes(stream, 4) for _ in xrange(n))

    for b0, b1, b2, b3 in bytes:
        in_width = (((((b3 * z) // 0o400) + (b2 * z)) // 0o400) + (b1 * z)) // beta
        if b0 > 0:
            if b0 < 255:
                raise RuntimeError('Invalid width in TFM file')
            else:
                in_width -= alpha

        yield in_width


# This is the order of fields in the font
#    'lf', 'lh', 'bc', 'ec', 'nw', 'nh',
#    'nd', 'ni', 'nl', 'nk', 'ne', 'np'

class FontMetrics(object):
    def __init__(self, fontname, scale, d=None, n=None):
        self.n = n
        self.d = d
        self.name = fontname

        filename = kpsewhich('%s.tfm' % fontname)

        with open(filename, 'r') as f:
            stream = iter(bytearray(f.read()))

        lengths = read_array(stream, I2, 12)

        header = read_array(stream, I4, lengths[1])
        self.size = (header[1] / float(1<<20)) * (float(scale) / self.d)
        bc = lengths[2]
        ec = lengths[3]
        nc = 1 + ec - bc
        char_info = read_bytes(stream, 4 * nc)

        widths = list(tfm_widths(stream, lengths[4], scale))
        heights = list(tfm_widths(stream, lengths[5], scale))
        depths = list(tfm_widths(stream, lengths[6], scale))

        it = iter(char_info)

        chars = []
        for i in xrange(bc, 1+ec):
            width_ix = next(it)
            b = next(it)
            height_ix = (0xf0 & b) >> 4
            depth_ix = 0x0f & b
            next(it)
            next(it)

            chars.append((i, (
                widths[width_ix],
                heights[height_ix],
                depths[depth_ix])))


        self.chars = dict(chars)


# Dispatchers
class Dispatcher(object):
    """Hides a _lot_ of the complexity / boilerplate"""
    def __init__(self):
        self.ops = {}

    # A contextmanager that returns a decorator. What could be simpler? :)
    @contextmanager
    def op(self):
        def op(*opcodes):
            """Add entry to the dispatcher"""
            def f(func):
                for opcode in opcodes:
                    self.ops[opcode] = func
                return func
            return f
        yield op
        self._make_tables()


    def _make_tables(self):
        # For efficiency and convenience, we define two tables at compile
        # (import) time. One is the lookup table, which returns a set for 
        ops = self.ops
        sorted_ops = sorted(ops.iteritems(), key=operator.itemgetter(0))
        dispatch = dict()
        lookup = dict()

        for (a, func), (b, _) in itertools.izip(sorted_ops, sorted_ops[1:]):
            d = b - a

            if d > 1:
                for i, j in enumerate(xrange(a, b), 1):
                    dispatch[j] = partial(func, i)
            elif d == 1:
                dispatch[a] = partial(func, 0)
            elif d == 0:
                raise RuntimeError('Overlapping opcodes')

            fn = func.func_name
            s = lookup.get(fn, set())
            s.update(xrange(a, b))
            lookup[fn] = s
        self.lookup = lookup
        self.dispatch = dispatch


    def reader(self, whitelist=(), blacklist=(), end_on=()):

        dispatch = self.dispatch
        lookup = self.lookup

        if whitelist and blacklist:
            raise RuntimeError(
                'Cannot have both whitelist and blacklist')

        end_on = set().union(*(lookup[i] for i in end_on))

        if whitelist:
            whitelist = set().union(*(lookup[i] for i in whitelist))
            return WhitelistReader(whitelist, end_on, dispatch)

        elif blacklist:
            blacklist = set().union(*(lookup[i] for i in blacklist))
            return BlacklistReader(blacklist, end_on, dispatch)


class WhitelistReader(object):
    def __init__(self, whitelist, end_on, dispatch):
        self.whitelist = whitelist
        self.end_on = end_on
        self.dispatch = dispatch

    def __call__(self, stream, state):
        dispatch = self.dispatch
        whitelist = self.whitelist
        end_on = self.end_on

        while True:
            opcode = next(stream)
            if opcode in whitelist:
                dispatch[opcode](stream, state)
            else:
                raise RuntimeError('Opcode %d not in whitelist' % opcode)

            if opcode in end_on:
                return


class BlacklistReader(object):
    def __init__(self, blacklist, end_on, dispatch):
        self.blacklist = blacklist
        self.end_on = end_on
        self.dispatch = dispatch

    def __call__(self, stream, state):
        dispatch = self.dispatch
        blacklist = self.blacklist
        end_on = self.end_on

        while True:
            opcode = next(stream)
            if opcode not in blacklist:
                dispatch[opcode](stream, state)
            else:
                raise RuntimeError('Opcode %d in blacklist' % opcode)

            if opcode in end_on:
                return


def default_char(state, char): pass
def default_rule(state, a, b): pass
def default_fnt_def(fnt): pass
def default_fnt(state, fnt, i): pass

class DviState(object):
    __slots__ = ('on_put_char', 'on_put_rule', 'on_fnt_def', 'on_fnt',
                 'fonts', 'font', 'stack', 'h', 'v', 'w', 'x', 'y', 'z',
                 'num', 'den', 'mag')
    def __init__(self):
        self.fonts = {}
        self.font = None
        self.set_callbacks()
        self.stack = []
        self.state = 0, 0, 0, 0, 0, 0

    def attach_handler(self, handler):
        for cb in ('on_put_char', 'on_put_rule', 'on_fnt_def', 'on_fnt'):
            try:
                setattr(self, cb, getattr(handler, cb))
            except AttributeError:
                pass

    def set_callbacks(self,
                      char=default_char,
                      rule=default_rule,
                      fnt_def=default_fnt_def,
                      fnt=default_fnt):
        self.on_put_char = char
        self.on_put_rule = rule
        self.on_fnt_def = fnt_def
        self.on_fnt = fnt

    @property
    def state(self):
        return (self.h, self.v, self.w,
                self.x, self.y, self.z)

    @state.setter
    def state(self, (h, v, w, x, y, z)):
        self.h = h
        self.v = v
        self.w = w
        self.x = x
        self.y = y
        self.z = z

    def push(self):
        self.stack.append(self.state)

    def pop(self):
        self.state = self.stack.pop()


# The TexSizer is an example of the handler interface.
class TexSizer():
    def __init__(self):
        self.left = 0
        self.right = 0
        self.top = 0
        self.bottom = 0

    def on_put_char(self, s, i):
        st = s
        w, h, d = s.font.chars[i]
        self.left = min(self.left, st.h, st.h + w)
        self.right = max(self.right, st.h, st.h + w)

        self.top = min(self.top, st.v - h)
        self.bottom = max(self.bottom, st.v + d)

    def on_put_rule(self, s, a, b):
        v, h = s.v, s.h
        self.left = min(self.left, h, h + b)
        self.right = max(self.right, h, h + b)

        self.top = min(self.top, v, v + a)
        self.bottom = max(self.bottom, v, v + a)

    @property
    def size(self):
        return (self.right - self.left, self.bottom - self.top)

    @property
    def bl(self):
        return self.left, self.bottom

    def reset(self):
        size = self.size, self.bl
        self.left = 0
        self.right = 0
        self.top = 0
        self.bottom = 0
        return size


# This is probably the most complicated dispatcher. Dispatchers are objects that
# dispatch on an opcode, and loop until a certain final opcode is met. They can be
# operated on a whitelist or blacklist basis, thus tightening up parsing without
# exceptional logic. They operate based upon an internal dispatch dictionary,
# which maps from opcodes to the functions defined below. Function names are
# given here.

# Whilst this may seem slightly unorthodox (why not use a class?), done at a
# class level every method should really be a class method, as threading state
# creates a very limited parser which cannot be arbitrarily redirected.
# Furthermore, by explicitly passing the state object, fewer lookups have to be
# performed and namespace pollution is reduced.

# Mappings are created automatically based upon the following idea: opcodes
# spread to the next opcode, and a value starting from 1 is passed as the first
# argument. If an opcode is followed immediately by another, it must have value
# zero. As such, single operation opcodes get passed zero. This convention
# allows for a reduction of duplication, and still allows all the flexibility
# required.

dvi = Dispatcher()
with dvi.op() as op:

    @op(0, 1)
    def set_char_i(i, stream, state):
        """Typeset the character with code i and move right by its width"""
        state.on_put_char(state, i)
        state.h += state.font.chars[i][0]

    @op(128)
    def set_char(n, stream, state,
                set_char_i=set_char_i,
                 unsigned=unsigned):
        """
        Typeset the character contained in the n-byte parameter and move
        right by its width

        """
        set_char_i(unsigned[n](stream), stream, state)

    @op(133)
    def put_char(n, stream, state,
                 unsigned=unsigned):
        state.on_put_char(state, unsigned[n](stream))

    @op(137)
    def put_rule(_, stream, state, fmt=fmt(i4, i4)):
        a, b = fmt(stream)
        state.on_put_rule(state, a, b)
        return b

    @op(132)
    def set_rule(_, stream, state, put_rule=put_rule):
        state.h += put_rule(_, stream, state)

    @op(138)
    def nop(_, stream, state):
        """By definition does nothing"""
        return

    @op(139)
    def bop(_, stream, state, i4=i4, I4=I4):
        c = read_array(stream, I4, 10)
        p = i4(stream)

    @op(140)
    def eop(_, stream, state):
        return

    @op(141)
    def push(_, stream, state):
        state.push()

    @op(142)
    def pop(_, stream, state):
        state.pop()

    @op(143)
    def right(n, stream, state, signed=signed):
        state.h += signed[n](stream)

    @op(147, 148)
    def w(n, stream, state, signed=signed):
        """Move right by w"""
        if n:
            state.w = signed[n](stream)
        state.h += state.w

    @op(152, 153)
    def x(n, stream, state, signed=signed):
        """Move right by x"""
        if n:
            state.x = signed[n](stream)
        state.h += state.x

    @op(157)
    def down(n, stream, state,signed=signed):
        state.v += signed[n](stream)

    @op(161, 162)
    def y(n, stream, state, signed=signed):
        """Move down by y"""
        if n:
            state.y = signed[n](stream)
        state.v += state.y

    @op(166, 167)
    def z(n, stream, state, signed=signed):
        if n:
            state.z = signed[n](stream)
        state.v += state.z

    @op(171, 172)
    def fnt_num_i(i, stream, state):
        state.font = state.fonts[i]
        state.on_fnt(state, state.font, i)

    @op(235)
    def fnt(n, stream, state, unsigned=unsigned):
        i = unsigned[n](stream)
        fnt_num_i(i, stream, state)

    @op(239)
    def xxx(n, stream, state, unsigned=unsigned, read_string=read_string):
        l = unsigned[n](stream)
        read_string(stream, l)

    @op(243)
    def fnt_def(n, stream, state,
                unsigned=unsigned,
                fmt=fmt(I4, I4, I4, I1, I1),
                Font=FontMetrics
               ):
        k = unsigned[n](stream)
        c, s, d, a, l = fmt(stream)
        name = read_string(stream, a + l)

        state.fonts[k] = font = Font(name, s, d, k)

        state.on_fnt_def(font)

    @op(247)
    def pre(_, stream, state,
            fmt=fmt(I1,I4,I4,I4,I1),
            read_string=read_string
           ):
        i, num, den, mag, k = fmt(stream)
        state.num = num
        state.den = den
        state.mag = mag
        x = read_string(stream, k)

    @op(248)
    def post(_, stream, state):
        # We really have no need to disturb the postamble, as we read in
        # files sequentially
        raise(RuntimeError, 'Postamble detected in unexpected place')

    @op(249)
    def post_post(_, stream, state):
        # Nor do we have reason to read in post post
        raise(RuntimeError, 'Post-postamble detected in unexpected place')

    @op(250)
    def undefined(_, stream, state):
        raise(RuntimeError, 'Undefined opcode')

vf = Dispatcher()
with vf.op() as op:
    def _add_char(pl, cc, tfm, stream, state):
        dvi = read_string(stream, pl)
        state.chars[cc] = dvi

    @op(247)
    def pre(_, stream, state,
            read_string=read_string,
            fmt1=fmt(I1, I1), fmt2=fmt(I4, I4)):
        i, k = fmt1(stream)
        x = read_string(stream, k)
        cs, ds = fmt2(stream)

    @op(0, 1)
    def short_char_i(pl, stream, state,
                     _add_char=_add_char,
                     fmt=fmt(I1, I3)):
        cc, tfm = fmt(stream)
        _add_char(pl, cc, tfm, stream, state)

    @op(242)
    def long_char_i(i, stream, state,
                    _add_char=_add_char,
                    fmt=fmt(I4, I4, I4)):
        pl, cc, tfm = fmt(stream)
        _add_char(pl, cc, tfm, stream, state)

    @op(243)
    def fnt_def(n, stream, state,
                fmt=fmt(I4, I4, I4, I1, I1),
                Font=FontMetrics):

        k = unsigned[n](stream)
        c, s, d, a, l = fmt(stream)
        n = read_string(stream, a + l)
        state.fonts[k] = Font(n, s, d, k)

    @op(248)
    def post(_, stream, state):
        pass

    @op(249)
    def undef(i, stream, state):
        pass

class VfState(object):
    __slots__ = 'fonts', 'chars', 'scale'
    def __init__(self):
        self.fonts = {}
        self.chars = {}

read_pre = dvi.reader(whitelist=['pre', 'nop'], end_on=['pre'])
read_bop = dvi.reader(whitelist=['bop', 'nop', 'fnt_def'], end_on=['bop'])
read_eop = dvi.reader(blacklist=['pre', 'post', 'post_post'], end_on=['eop'])
read_vf = dvi.reader(blacklist=['pre', 'post', 'post_post'], end_on=['eop'])
vf_read_pre = vf.reader(whitelist=['pre'], end_on=['pre'])
vf_read_main = vf.reader(blacklist=['pre'], end_on=['post'])

class T1Font(object):
    """
    TeX has Type 1 fonts. This class represents those.

    """
    def __init__(self, filename, font, enc, scale=1.0):
        self.enc = enc
        self.fontcore = filename, scale * font.size

    def render(self, renderer, state, char):
        if self.enc:
            char = self.enc[char]
        c = 'c', DVI2PT * state.h, DVI2PT * state.v, char, self.fontcore
        renderer.page.append(c)


class VirtualFont(object):
    """
    TeX has virtual fonts. This class represents those.

    """
    def __init__(self, filename, texfont,
                 read_pre=vf_read_pre, read_main=vf_read_main):
        self.state = VfState()

        with open(filename) as f:
            stream = iter(bytearray(f.read()))

        read_pre(stream, self.state)
        read_main(stream, self.state)

        self.font = self.state.fonts[0]
        self.texfont = texfont

        self.psfonts = psfonts = {}

        for i, j in self.state.fonts.iteritems():
            names, pfbs, encs, psopts = fontmap.get(j.name)
            psname = pfbs[0]
            encs = (encs and encs[0][1]) or None
            psfonts[i] = T1Font(psname, j, encs, texfont.size)


    def render(self, renderer, state, i, read_vf=read_vf):
        renderer.in_vf=True
        stream = iter(bytearray(self.state.chars[i]))

        texfont = state.font
        texfonts = state.fonts
        font = renderer.font
        fonts = renderer.fonts

        state.fonts = self.state.fonts
        state.font = self.font
        renderer.fonts = self.psfonts
        renderer.font = self.psfonts[0]

        state.push()

        state.w = 0
        state.x = 0
        state.y = 0
        state.z = 0

        # This must be in a try block because the dvi commands can just exit
        # completely unexpectedly.
        try:
            read_vf(stream, state)
        except TypeError:
            pass
        except StopIteration:
            pass


        state.pop()

        state.font = texfont
        state.fonts = texfonts
        renderer.font = font
        renderer.fonts = fonts
        renderer.in_vf = False


class DviSlave():
    # Since we ignore specials and all that nonsense, we only need to store a
    # list of fonts, characters, and their positions. We can use a dispatcher
    # pattern to make this work -- have a heterogenous list with various objects
    # representing the renderings to perform. So really, all this does is handle
    # virtual fonts and compile things down into DVI objects. So for instance,
    # there will be lots and lots of tiny glyph objects.
    def __init__(self):
        self.fonts = {}
        self.page = []
        self.sizer = TexSizer()
        self.in_vf = False

    def clear_page(self):
        page = self.page
        (w, h), (b, l) = self.sizer.reset()
        size = DVI2PT * w, DVI2PT * h
        bl = DVI2PT * b, DVI2PT * l
        self.page = []
        return page, size, bl

    def on_put_char(self, state, i):
        self.font.render(self, state, i)
        # But if it's a virtual font how do we tell? ARRGH!
        # After about ~1min of thinking, this inelegant solution was proposed!
        if not self.in_vf:
            self.sizer.on_put_char(state, i)

    def on_fnt_def(self, texfont):
        r = fontmap.get(texfont.name)
        if r:
            names, pfbs, encs, psopts = r
            psname = pfbs[0]
            enc = encs[0][1] if encs else None
            font = T1Font(psname, texfont, enc)
        else:
            vffile = kpsewhich('%s.vf' % texfont.name)
            font = VirtualFont(vffile, texfont)

        self.fonts[texfont.n] = font

    def on_fnt(self, state, fnt, k):
        self.font = self.fonts[k]

    def on_put_rule(self, s, a, b):
        rule = 'r', DVI2PT * s.h, DVI2PT * s.v, DVI2PT * b, DVI2PT * a
        self.page.append(rule)
        self.sizer.on_put_rule(s, a, b)

# This is something
def texparser():
    """
    A parser for tex output supplied in dribs and drabs.

    """
    def texparser():
        page_re = re.compile(r'\[(\d+)\s*\]')
        errors_re = re.compile(r'^\(That makes 100 errors; please try again.\)$')

        mode = 0
        page = 0

        while True:
            lines = yield


            for line in lines:
                if mode == 0:
                    if line.startswith('!') and line != lines[-1]:
                        mode = 1
                        errors = [line[1:]]

                    else:
                        np = [int(i.group(1)) for i in page_re.finditer(line)]
                        if not np:
                            if errors_re.match(line):
                                yield (2, None)
                            continue

                        np = [i for i in np if i > page]
                        for n in np:
                            page = n
                            yield (0, page)


                elif mode == 1 and line != lines[-1]:
                    if len(errors) >= 3:
                        yield (1, "\n".join(errors))
                        mode = 0
                    else:
                        errors.append(line)

    def trampoline(g, h):
        while True:
            x = yield
            k, = g.feed(x)
            for i in h.feed(k):
                yield i

    class GenWrap(object):
        def __init__(self, gen):
            self._gen = gen
            self._gen.next()

        def feed(self, i):
            x = self._gen.send(i)
            while True:
                if x is None:
                    break
                yield x
                x = next(self._gen, None)

    def lineparser():
        buf = ""
        while True:
            buf += yield
            lines = buf.split('\n')
            buf = lines[-1]
            yield lines

    g = GenWrap(lineparser())
    h = GenWrap(texparser())

    return GenWrap(trampoline(g, h))

# Python 2 / 3 compat. Need to do some other work here and there!

def mkfifos(*filenames):
    for filename in filenames:
        try:
            os.remove(filename)
        except OSError:
            pass

    for filename in filenames:
        os.mkfifo(filename)

# documentclass?
# arbitrary TeX?

DEFAULT_TEMPLATE_STR = r"""

\documentclass[12pt]{article}
\usepackage[T1]{fontenc}
\usepackage[active]{preview}
\usepackage{microtype}
\usepackage[T1]{fontenc}
\usepackage[]{eulervm}

\def\startpage{\begin{preview}}
\def\stoppage{\end{preview}}

%Additional packages
\additionalpackages

\begin{document}

\pages

\end{document}

""".strip()


class TexTemplate(object):
    """
    Process a TeX template object. The TeX template format is quite natural
    from a TeX point of view, and allows for avoiding the preview package by
    use of page breaks etc.

    """
    def __init__(self, template_string):
        self.packages = []
        self.pre, self.post = template_string.split('\pages')
        def_re = re.compile(r'\\def\\(.*?){(.*)}\s*%?.*$')

        for i in self.pre.split('\n'):
            m = def_re.match(i)
            if m:
                name = m.group(1)
                val = m.group(2)
                if name in {'startpage', 'stoppage'}:
                    setattr(self, name, val)

    def add_package(self, package, *opts):
        self.packages.append((package, opts))
        return self

    @staticmethod
    def show_package(package, opts):
        return (r"\usepackage[%s]{%s}" % (",".join(opts), package)
                if opts else r"\usepackage{%s}" % package)

    @property
    def preamble(self):
        return self.pre.replace(r'\additionalpackages', "\n".join(
            self.show_package(package, opts)
            for package, opts in self.packages))

    @property
    def postamble(self):
        return self.post

    def page(self, content):
        return "%s\n%s\n%s" % (self.startpage, content, self.stoppage)


DEFAULT_TEMPLATE = TexTemplate(DEFAULT_TEMPLATE_STR)


def queue_iter(queue):
    """
    Create an iterator over a queue of iterables (e.g. strings or
    bytearrays)

    """
    while True:
        x = queue.get()
        yield x


def remove(f):
    try:
        os.remove(f)
    except:
        pass


class SessionObject(object):
    def __init__(self, init, delete):
        init()
        self.delete = delete
    def __del__(self):
        self.delete()


class SessionProcess(object):
    """Process that lives and dies with the session"""
    def __init__(self, args, stdin=sp.PIPE, stdout=sp.PIPE, depends=()):
        self.depends = depends
        self.process = sp.Popen(
            args, stdin=stdin, stdout=stdout,
            stderr=sp.PIPE, preexec_fn = os.setpgrp,
            close_fds=True)
    def kill(self):
        self.process.kill()

    def __del__(self):
        try:
            self.process.kill()
        except AttributeError:
            pass


def feed_input(filename, input_queue):
    """The thread that will feed the input into the pipe that latex reads from"""
    f = open(filename, 'wb', 0)
    fd = f.fileno()

    os.write(fd, '\n')
    # This is where the *magic* happens.  We should really wait for a TexReady
    # event, but ah well! That fun is yet to come!
    time.sleep(0.2)
    while True:
        os.write(fd, input_queue.get())


def iterator_reader(f):
    fd = f.fileno()
    while True:
        x = os.read(fd, 8092)
        if not x:
            return
        yield x


def watch_stdout(f, output_queue):
    """Watch the output of latex and feed back errors etc."""
    # We use os.read so that we can have a decent buffer but we don't block
    # waiting for it.
    tp = texparser()
    xs = iterator_reader(f)
    xs, ys = itertools.tee(xs)
    parsings = itertools.imap(tp.feed, xs)

    errors = []
    for c, n in itertools.chain.from_iterable(parsings):
        if c is 0:
            output_queue.put((n, errors))
            errors = []
        elif c is 1:
            errors.append(n)
        else:
            errors.append(n)
            output_queue.put((-1, errors))
            errors = []


def read_output(filename, output_queue, sync):
    """Watch the output of latex and feed back errors etc."""
    f = open(filename, 'rb', 0)

    state = DviState()
    slave = DviSlave()
    state.attach_handler(slave)

    xs = itertools.chain.from_iterable(bytearray(i) for i in iterator_reader(f))


    read_pre(xs, state)
    while True:
        sync.acquire()
        read_bop(xs, state)
        read_eop(xs, state)
        output_queue.put(slave.clear_page())

def daemon(target, *args):
    t = threading.Thread(target=target, args=args)
    t.daemon = True
    t.start()
    return t

class TempDir(object):
    def __init__(self, dir, prefix):
        self.path = tempfile.mkdtemp(prefix=prefix, dir=None)

    def named_pipe(self, name):
        filename = os.path.join(self.path, name)
        os.mkfifo(filename)
        return filename

    def close(self):
        shutil.rmtree(self.path)

    def __del__(self):
        try:
            shutil.rmtree(self.path)
        except:
            pass

class TexDaemon(object):
    def __init__(self, template=None, dir=None):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.watch_queue = queue.Queue()
        self._template = template or DEFAULT_TEMPLATE

        self.tempdir = TempDir(dir, prefix='texlet_')

        tex_pipe = self.tempdir.named_pipe('texlets.tex')
        dvi_pipe = self.tempdir.named_pipe('texlets.dvi')

        self.sync = threading.Semaphore(0)

        self._tex = SessionProcess(
            ['latex', '-output-directory', self.tempdir.path,
             '-interaction=nonstopmode', '-ipc', tex_pipe],
        )
        os.write(self._tex.process.stdin.fileno(),'X'*10)

        self._writer_thread = daemon(feed_input, tex_pipe, self.input_queue)
        self._watcher_thread = daemon(watch_stdout, self._tex.process.stdout,
                                      self.watch_queue)
        self._reader_thread = daemon(read_output, dvi_pipe,
                                     self.output_queue, self.sync)


        self._put(self._template.preamble)

        self._output = itertools.chain.from_iterable(
            queue_iter(self.output_queue))

        p = self._template.page('\LaTeX')
        self._put(p + '\n\n')
        self.sync.release()
        self.watch_queue.get(timeout=5)
        self.output_queue.get()

    # TODO: Restart??? Error handling...

    def page(self, tex):
        p = self._template.page(tex)
        #print(p)
        self._put(p + '\n\n')
        self.sync.release()
        try:
            w = self.watch_queue.get(timeout=1.0)
            o = self.output_queue.get(timeout=1.0)
        except:
            self._tex.kill()
            self.tempdir.close()
            raise RuntimeError('LaTeX has most probably crashed -- perhaps bad input?')
        return w, o

    def _put(self, lines):
        # Want an Async wrapper around thread get
        self.input_queue.put(lines + '\n')

    def join(self):
        p = self._template.postamble
        #print(p)
        self._put(p)
        self._watcher_thread.join()

    def __del__(self):
        try:
            self.join()
        except:
            pass
