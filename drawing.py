import math
import itertools
import Queue as queue
import multiprocessing as mp
import cairo
import _freetype
import tex

# We could quite easily simplify most of this by using a 'new' (2010)
# RecordingSurface from Cairo,  but then we would lose a lot of the niceness of
# being able to inspect in Python.  As it's already implmented, we'll leave it
# as so.  Also, RecordingSurface has no notion of subpictures, so this is subtly
# more powerful. Finally, using Cairo's RecordingSurface removes the possibility
# of using this on really old and outdated systems.

# This is perhaps over-engineered. We need threads, and little else. But this
# *does* work... So for now, it stays.

# I had actually forgotten how *simple* a lot of this is. With the right
# guidance, it could actually be rather good.

class CairoBackend(object):

#    def show(self, pic, block):
#        try:
#            self.gui.show(pic, block)
#        except AttributeError:
#            gui = GuiRemote()
#            gui.show(pic, block)
#            self.gui = gui


    def save(self, picture, filename, filetype):
        # Determine the filetype automatically from filename
        #surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 300, 300)

        dx, dy, w, h = self.size(picture)

        surf = cairo.PDFSurface(filename, w - dx, h - dy)
        cr = cairo.Context(surf)
        cr.translate(-dx, -dy)
        #cr.save()
        #cr.set_source_rgb(1,1,1)
        #cr.paint()
        #cr.restore()
        CairoRenderer(cr).draw_picture(picture)
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

    def draw_text(self):
        # This will, in the near future, draw text
        pass

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


class GtkViewer(object):
    def __init__(self, picture, backend):
        import gtk
        self._picture = picture
        self._backend = backend
        self._window = gtk.Window()
        self._da = gtk.DrawingArea()

        self._da.connect('expose-event', self._redraw)

        self._window.connect('destroy', self._destroy)

        self._window.add(self._da)
        self._window.show_all()


    def set_picture(self, picture=None):
        self._picture = picture or self._picture
        self._da.queue_draw()

    def _destroy(self, win):
        gtk.main_quit()

    def _redraw(self, da, ev):
        # Use the scale given by the thing itself
        cr = da.window.cairo_create()
        x0, y0, x1, y1 = self._backend.size(self._picture)
        w = x1 - x0
        h = y1 - y0

        ww, wh = da.window.get_size()

        mw = mh = 2

        scale = min(
            float(ww - 2*mw) / w ,
            float(wh - 2*mh) / h 
        )

        dx = 0.5 * (ww - scale*w)
        dy = 0.5 * (wh - scale*h)

        # Cairo commands
        # Draw background
        cr.save()
        cr.set_source_rgb(0, 0, 0)
        cr.paint()

        cr.set_source_rgb(0.9, 0.1, 0.1)
        cr.rectangle(dx - mw, dy - mh, w*scale + 2*mw, h*scale + 2*mh)
        cr.fill()
        cr.restore()

        cr.translate(dx, dy)
        cr.scale(scale, scale)
        cr.translate(-x0, -y0)
        cr.save()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(x0, y0, w, h)
        cr.fill()
        cr.restore()

        self._backend.draw_to_context(self._picture, cr)

    def run(self):
        gtk.main()



class GuiRemote(object):
    def show(self, picture, block=True):
        # If the GUI is running...
        # Let's make sure we send it the new information
        try:
            # TODO: There's a subtle race condition here
            if self.process.is_alive():
                self.queue.put(picture)
            else:
                raise AttributeError
        except AttributeError:
            self.queue = mp.Queue()
            self.process = mp.Process(target=GuiRemote_run_gui, args=(self.queue,))
            import __main__ as main
            self.process.daemon = True
            self.process.start()

            self.queue.put(picture)

            #interactive = __name__ != '__main__'
            #block = block and not interactive

            if block:
                try:
                    self.process.join()
                except KeyboardInterrupt:
                    pass


def GuiRemote_run_gui(queue):
    import gobject
    import gtk
    import threading

    backend = CairoBackend()

    gobject.threads_init()

    viewer = GtkViewer(queue.get(), backend)

    def queue_watcher():
        viewer.set_picture(queue.get())

    t = threading.Thread(target=queue_watcher)
    t.daemon=True
    t.start()

    try:
        viewer.run()
    except KeyboardInterrupt:
        pass

    queue.close()


default_units = {
    'mm': (0.35277777777777777778, 2.83464566929133858268),
    'cm': (0.03527777777777777778, 28.34645669291338582677),
    'inches': (0.01388888888888888889, 72.00),
    'tp': (1.00375, 0.99626400996264009963),
    'pt': (1, 1),
}


default_backend = CairoBackend()

class Picture(object):
    """A drawing is a sequence of commands."""
    __slots__ = ['commands', 'backend', '_units', '_default_units']


    def __init__(self, commands=None, backend=default_backend, units=default_units):
        self.commands = [] if commands is None else commands
        self.backend = backend
        self._default_units = units.get('default', 'pt')
        self._units = default_units

    def _cput(self, *args):
        self.commands.append(args)
        return self
    
    def subpicture(self, commands=None):
        """
        Create a picture which is added to this picture. Return new
        sub-picture.

        """
        subpic = Picture(commands if commands is not None else [])
        self._cput('picture', subpic)
        return subpic

    def picture(self, picture):
        """
        Create a picture which is added to this picture. Return new
        sub-picture.

        """
        return self._cput('picture', picture)

    def source_rgb(self, r, g, b):
        return self._cput('source_rgb', r, g, b)

    def move_to(self, x, y):
        return self._cput('move_to', x, y)

    def line_to(self, x, y):
        return self._cput('line_to', x, y)

    def curve_to(self, x, y):
        return self._cput('curve_to', x, y)

    def stroke(self):
        return self._cput('stroke')

    def rectangle(self, x, y, w, h):
        """
        Add a rectangle from (x, y) to (x+w, x+h).

        """
        return self._cput('rectangle', x, y, w, h)

    def linecap(self, captype):
        return self._cput('set_line_cap', captype)

    def linejoin(self, jointype):
        return self._cput('set_line_join', jointype)

    def arc(self, x=0, y=0, radius=1.0, start=0, stop=360):
        """
        Create an arc at x and y. Defaults to a complete unit circle at the
        origin.

        """
        self._cput('circle', x, y, radius, start, stop)
        return self

    def rotate(self, angle):
        """
        Return a subpicture that has been rotated by `angle` degrees.

        """
        return self.subpicture([('rotate', angle)])

    def scale(self, sx, sy=None):
        """
        Return a subpicture that has been scaled by `sx` and `sy` degrees.

        """
        return self.subpicture([('scale', sx, sy or sx)])

    def shift(self, dx, dy):
        """
        Return a subpicture that has been shifted by `dx` and `dy` units.

        """
        return self.subpicture([('shift', dx, dy)])


    def linewidth(self, w=2.0):
        return self._cput('set_line_width', w)

    def save(self, filename, filetype='auto'):
        """
        Save the picture to a file.

        """
        return self.backend.save(self, filename, filetype)



    def show(self, block=False):
        """
        Show the picture.

        """
        return self.backend.show(self, block)

    def size(self):
        """
        Show the picture.

        """
        return self.backend.size(self)

    def defaultUnit(self, name):
        self._default_units = name

    # Everything remains in pts underneath! Too looney to consider otherwise!
    def units(self, old_units, new_units, x, y):
        if old_units == new_units:
            return (x, y)
        s = self._units[old_units][1] * self._units[new_units][0]
        return (s * x, s * y)


    def cursor(self, x=0, y=0, units=None):
        """
        Creates and returns a new cursor from this picture.

        """
        units = units or self._default_units
        return cursor.Cursor(self, x, y, units)

    def __repr__(self):
        return '<Picture(%r)>' % self.commands


p = Picture()
p.move_to(0, 0).linecap('round').line_to(10,10).stroke()
p.save('output.pdf')


td = tex.TexDaemon('test.tex').start()
print td.page('page')
