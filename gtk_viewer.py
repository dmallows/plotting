# Let's start with a simple picture
import gtk
from deps import depman

class GtkViewer(object):
    @depman.require(backend='backend')
    def __init__(self, picture, backend):
        self._picture = picture
        self.backend = backend
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
        x0, y0, x1, y1 = self.backend.size(self._picture)
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

        self.backend.draw_to_context(self._picture, cr)

    def run(self):
        gtk.main()
