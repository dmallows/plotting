import ctypes as c
import ctypes.util
import cairo
import itertools
import operator

FT = c.cdll.LoadLibrary(ctypes.util.find_library('freetype'))

class FT_Library_Rec(c.Structure): pass

class FT_Face_Rec(c.Structure): pass

# Utility declarations

ptr = c.pointer
PTR = c.POINTER

# Declarations
FT_Library = PTR(FT_Library_Rec)
FT_Face = PTR(FT_Face_Rec)
FT_Error = c.c_int
FT_UINT = c.c_uint
FT_LONG = c.c_long
FT_ULONG = c.c_ulong
FT_STRING = c.c_char_p

ADOBE_CUSTOM = c.c_uint32(
    (ord('A') << 24) | (ord('D') << 16) | (ord('B') << 8) | ord('C')
)


# Function types
FUNCTIONS = [
    ('Init_FreeType', [PTR(FT_Library)], FT_Error),
    ('New_Face', [FT_Library, FT_STRING, FT_LONG, PTR(FT_Face)], FT_Error),
    ('Get_Name_Index', [FT_Face, FT_STRING], FT_UINT),
    ('Get_Char_Index', [FT_Face, FT_ULONG], FT_UINT),
    ('Select_Charmap', [FT_Face, c.c_uint32], FT_Error)
]

for f, argtypes, restype in FUNCTIONS:
    f = getattr(FT, 'FT_%s' % f)
    setattr(f, 'argtypes', argtypes)
    setattr(f, 'restype', restype)

# Initialisation
LIB = FT_Library()
LIB_P = ptr(LIB)
FT.FT_Init_FreeType(LIB_P)
CAIRO = c.cdll.LoadLibrary(ctypes.util.find_library('cairo'))

class cairo_font_face_t(c.Structure): pass
class cairo_t(c.Structure): pass

CAIRO_FUNCS = [
    ('ft_font_face_create_for_ft_face', [FT_Face, c.c_int], PTR(cairo_font_face_t)),
    ('set_font_face', [PTR(cairo_t), PTR(cairo_font_face_t)], c.c_int)
]

class pycairo_context(c.Structure):
    _fields_ = [('head', ctypes.c_byte * object.__basicsize__),
                ('ctx', PTR(cairo_t)),
                ('base', ctypes.c_void_p)]

for f, argtypes, restype in CAIRO_FUNCS:
    f = getattr(CAIRO, 'cairo_%s' % f)
    setattr(f, 'argtypes', argtypes)
    setattr(f, 'restype', restype)


class Face(object):
    # This is the hashing scheme
    _context = None, None

    def __init__(self, name, index=0):
        self.face = FT_Face()
        self._as_parameter_ = self.face
        FT.FT_New_Face(LIB, name, 0, ptr(self.face))
        self._cairoface = CAIRO.cairo_ft_font_face_create_for_ft_face(self.face, 0)

    def select_charmap(self, encoding):
        return FT.FT_Select_Charmap(self, encoding)

    def get_name_index(self, chars):
        gni = FT.FT_Get_Name_Index
        return [gni(self, c) for c in chars]

    def get_char_index(self, chars):
        gci = FT.FT_Get_Char_Index
        return [gci(self, c) for c in chars]



    def set_cairo_font(self, cr, size):
        ref_cr, cr_p = Face._context
        if ref_cr is not cr:
            ref_cr, cr_p = Face._context =\
                    cr, pycairo_context.from_address(id(cr)).ctx

        CAIRO.cairo_set_font_face(cr_p, self._cairoface)
        cr.set_font_size(size)

first = operator.itemgetter(0)
fifth = operator.itemgetter(4)


class TextRenderer(object):
    def __init__(self):
        self._faces = {}

    def load(self, name):
        face = self._faces.get(name) or Face(name)
        self._faces[name] = face
        face.select_charmap(ADOBE_CUSTOM)
        return face

    def render(self, cr, dvi, groupby=itertools.groupby):
        # This is fucked!
        for op, xs in groupby(dvi[0], key=first):
            if op == 'c':
                for font, chars in groupby(xs, key=fifth):
                    fn, fs = font
                    face = self.load(fn)
                    face.set_cairo_font(cr, fs)
                    _, x, y, c, __ = zip(*chars)

                    try:
                        c = face.get_name_index(c)
                    except:
                        c = face.get_char_index(c)

                    cr.show_glyphs(zip(c, x, y))

            elif op == 'r':
                for _, x0, y0, dx, dy in xs:
                    cr.rectangle(x0, y0, dx, -dy)
                    cr.fill()
                # do the rule thingy here
