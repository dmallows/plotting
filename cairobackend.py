import math
import itertools
import cairo
import tex
from deps import depman

# We could quite easily simplify most of this by using a 'new' (2010)
# RecordingSurface from Cairo,  but then we would lose a lot of the niceness of
# being able to inspect in Python.  As it's already implmented, we'll leave it
# as so.  Also, RecordingSurface has no notion of subpictures, so this is subtly
# more powerful. Finally, using Cairo's RecordingSurface removes the possibility
# of using this on really old and outdated systems.


class CairoBackend(object):
    def show(self, pic, block):
        try:
            self.gui.show(pic, block)
        except AttributeError:
            import gtk_gui
            gui = gtk_gui.GuiRemote()
            gui.show(pic, block)
            self.gui = gui

    def save(self, pic, filename, filetype):
        # Determine the filetype automatically from filename
        #surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 300, 300)
        surf = cairo.PDFSurface(filename, 300, 300)
        cr = cairo.Context(surf)
        #cr.save()
        #cr.set_source_rgb(1,1,1)
        #cr.paint()
        #cr.restore()
        CairoRenderer(cr).draw_picture(pic)
        #surf.write_to_png(filename)
        surf.finish()

    def draw_to_context(self, pic, cr):
        CairoRenderer(cr).draw_picture(pic)

    def size(self, picture):
        c = CairoSizer()
        c.size_picture(picture)
        return c.extents



class CairoRenderer(object):
    def __init__(self, cr):
        self._cr = cr

    def draw_picture(self, picture):
        self._cr.save()
        for op, arg in ((x[0], x[1:]) for x in picture.commands):
            self.draw(op, arg)
        self._cr.restore()


    def draw_rectangle(self, x, y, w, h):
        self._cr.rectangle(x, y, w, h)

    def draw_rotate(self, angle, radians=math.radians):
        self._cr.rotate(radians(angle))

    def draw_scale(self, xscale, yscale=None):
        yscale = yscale or xscale
        self._cr.scale(xscale, yscale)

    def draw_line_to(self, x, y):
        self._cr.line_to(x, y)

    def draw_move_to(self, x, y):
        self._cr.move_to(x, y)

    def draw_shift(self, dx, dy):
        self._cr.translate(dx, dy)

    def draw_source_rgb(self, r, g, b):
        self._cr.set_source_rgb(r, g, b)

    def draw_set_line_width(self, w):
        self._cr.set_line_width(w)

    _jointypes = {
        'miter': cairo.LINE_JOIN_MITER,
        'round': cairo.LINE_JOIN_ROUND,
        'bevel': cairo.LINE_JOIN_BEVEL }

    def draw_set_line_join(self, jointype, jointypes=_jointypes):
        self._cr.set_line_join(jointypes[jointype])

    _captypes = {
        'butt': cairo.LINE_CAP_BUTT,
        'round': cairo.LINE_CAP_ROUND,
        'square': cairo.LINE_CAP_SQUARE }

    def draw_set_line_cap(self, captype, captypes=_captypes):
        self._cr.set_line_cap(captypes[captype])

    def draw_save(self):
        self._cr.save()

    def draw_restore(self):
        self._cr.restore()

    def draw_stroke_preserve(self):
        self._cr.stroke_preserve()

    def draw_stroke(self):
        self._cr.stroke()

    def draw_fill(self):
        self._cr.fill()

    def draw_fill_preserve(self):
        self._cr.fill_preserve()

    def draw_tex(self):
        pass

    def draw(self, op, args):
        try:
            return getattr(self, ('draw_%s' % op))(*args)
        except AttributeError:
            if __debug__:
                raise
            else:
                raise ValueError('Instruction %s is not implemented' % op)

class CairoSizer(CairoRenderer):
    def __init__(self):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1, 1)
        self._cr = cairo.Context(surf)
        self.extents = None

    def size_picture(self, picture):
        self._cr.save()
        for op, arg in ((x[0], x[1:]) for x in picture.commands):
            self.size(op, arg)

        self._cr.restore()

    def _update_extents(self, extents):
        if self.extents is None:
            self.extents = extents
        else:
            e0 = self.extents
            ex = extents
            if extents != (0, 0, 0, 0):
                d2u = self._cr.user_to_device
                ex = d2u(*ex[:2]) + d2u(*ex[2:])
                self.extents = (min(ex[0], e0[0]), min(ex[1], e0[1]),
                                max(ex[2], e0[2]), max(ex[3], e0[3]))


    def size_fill(self):
        self._extents.append(self._cr.fill_extents())
        self._cr.fill()

    def size_fill_preserve(self):
        self._update_extents(self._cr.fill_extents())
        self._cr.fill_preserve()

    def size_stroke(self):
        # This is necessary to get extents in device space.
        w = 0.5 * self._cr.get_line_width()

        dxx, dxy = self._cr.user_to_device_distance(w, 0)
        dyx, dyy = self._cr.user_to_device_distance(0, w)

        sx = math.sqrt(dxx*dxx + dxy*dxy)
        sy = math.sqrt(dyx*dyx + dyy*dyy)

        sx = float(abs(sx - w)) / sx
        sy = float(abs(sy - w)) / sy

        dx = abs(sx * dxx - sy * dyx)
        dy = abs(sx * dxy - sy * dyy)

        self._cr.save()
        self._cr.identity_matrix()
        ex = self._cr.stroke_extents()
        ex = ex[0] - dx, ex[1] - dy , ex[2] + dx , ex[3] + dy
        self._cr.restore()
        self._update_extents(ex)

        self._cr.stroke()

    def size_stroke_preserve(self):
        self._update_extents(self._cr.stroke_extents())
        self._cr.stroke_preserve()

    def size(self, op, args):
        try:
            f = getattr(self, ('size_%s' % op))
        except AttributeError:
            return self.draw(op, args)
        else:
            f(*args)


depman.provide('backend', CairoBackend)
depman.provide('texdaemon', tex.TexDaemon)
