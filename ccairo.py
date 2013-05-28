import signal
from ctypes import (
    CDLL, Structure, POINTER as PTR, pointer as ptr,
    c_double, c_char_p, c_int, c_void_p, c_ulong, CFUNCTYPE
)
from ctypes.util import find_library

def open_lib(name):
    return CDLL(find_library(name))

def fn_fixup(ob, fns, prefix=''):
    for i,j in fns.iteritems():
        f = getattr(ob, prefix + i)
        restype = j[-1]
        argtypes = j[:-1]
        f.restype = restype
        f.argtypes = argtypes
        setattr(ob, i, f)

cairo = open_lib('cairo')

class cairo_t(Structure): pass
class cairo_surface_t(Structure): pass


cairo.p = PTR(cairo_t)
cairo.surface_p = PTR(cairo_surface_t)

cairo_functions = dict(
    pdf_surface_create=[c_char_p, c_double, c_double, cairo.surface_p],
    surface_finish = [cairo.surface_p],
    create=[cairo.surface_p, cairo.p],
    destroy=[cairo.p, None],
    save=[cairo.p, None],
    restore=[cairo.p, None],
    set_source_rgb=[cairo.p, c_double, c_double, c_double, None],
    set_source_rgba=[cairo.p, c_double, c_double, c_double, c_double, None],
    fill=[cairo.p, None],
    paint=[cairo.p, None],
    stroke=[cairo.p, None],
    
    # Paths
    line_to=[cairo.p, c_double, c_double, None],
    move_to=[cairo.p, c_double, c_double, None],
    close_path=[cairo.p, None],
)


fn_fixup(cairo, cairo_functions, prefix='cairo_')

# cairo_surface_t* cairo_pdf_surface_create(filename, width, height)

class PDFSurface(object):
    def __init__(self, filename, width, height):
        self._as_parameter_ = cairo.pdf_surface_create('foo.pdf', 100, 100)

    def finish(self):
        cairo.surface_finish(self)

class Context(object):
    def __init__(self, surface):
        self._as_parameter_ = cairo.create(surface)

    def destroy(self):
        cairo.destroy(self)

    def save(self):
        cairo.save(self)

    def restore(self):
        cairo.restore(self)

    def set_source_rgba(self, r, g, b, a=1.0):
        cairo.set_source_rgba(self, r, g, b, a)

    def fill(self):
        cairo.fill(self)

    def paint(self):
        cairo.paint(self)

    def line_to(self, x, y):
        cairo.line_to(self, x, y)

    def move_to(self, x, y):
        cairo.move_to(self, x, y)

    def close_path(self):
        cairo.close_path(self)



class GtkWidget(Structure): pass
gtk = open_lib('gtk-x11-2.0')
gobject = open_lib('gobject-2.0')
#print gtk

gtk.widget_p = PTR(GtkWidget)

fn_fixup(gtk, dict( 
    init = [c_int, PTR(PTR(c_char_p)), None],
    main = [None],
    main_quit = [None],
    window_new = [c_int, gtk.widget_p],
    widget_show_all = [gtk.widget_p, None],
    widget_show = [gtk.widget_p, None],
), 'gtk_')


class closure(Structure): pass
gobject.closure_p = PTR(closure)

fn_fixup(gobject, dict(
    signal_connect_closure = [c_void_p, c_char_p, gobject.closure_p, c_int, c_ulong],
    cclosure_new_object = [c_void_p, c_void_p, gobject.closure_p],
), 'g_')



connections = {
    'destroy': [gtk.object_p, ],
}


class Window(GtkWidget):
    callback_type = CFUNCTYPE(c_void_p, gtk.widget_p, c_void_p)

    def __init__(self):
        self._as_parameter_ = gtk.window_new(0)

    def show(self):
        gtk.widget_show(self)

    def connect(self, ):

        


cp = c_char_p()
gtk.init(0, ptr(ptr(cp)))

gtk.widget_show_all(k)

callback_type = CFUNCTYPE(c_void_p, gtk.widget_p, c_void_p)

def callback(x, p):
    gtk.main_quit()

closure = gobject.cclosure_new_object(callback_type(callback), k)
gobject.signal_connect_closure(k, "destroy", closure, 0)

signal.signal(signal.SIGINT, signal.SIG_DFL)
gtk.main()
