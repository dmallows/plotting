# This module doesn't even need cairo, but it's important that it does

from deps import depman

default_units = {
    'mm': (0.35277777777777777778, 2.83464566929133858268),
    'cm': (0.03527777777777777778, 28.34645669291338582677),
    'inches': (0.01388888888888888889, 72.00),
    'tp': (1.00375, 0.99626400996264009963),
    'pt': (1, 1),
}


class Picture(object):
    """A drawing is a sequence of commands."""
    __slots__ = ['commands', 'backend', '_units', '_default_units']

    @depman.require(backend='backend')
    def __init__(self, backend, commands=(),
                 units=default_units):
        self.backend = backend
        self.commands = list(commands)
        self._default_units = units.get('default', 'pt')
        self._units = default_units

    def _cput(self, *args):
        self.commands.append(args)
        return self

    def subpicture(self, commands=()):
        """
        Create a picture which is added to this picture. Return new
        sub-picture.

        """
        subpic = Picture(commands=commands)
        self._cput('picture', subpic)
        return subpic

    def picture(self, picture):
        """
        Create a picture which is added to this picture. Return new
        picture.

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

    def fill(self):
        return self._cput('fill')

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
        # We need a way to track all the transformations that have happened to
        # an object, either outside of cairo (the sensible) or by replaying the
        # transformation commands in a blank picture (less sensible due to
        # coupling)
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

    def tex(self, tex, x=0, y=0):
        return self._cput('tex', tex, x, y)

    def save(self, filename, filetype=None):
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


    def __repr__(self):
        return '<Picture(%r)>' % self.commands

