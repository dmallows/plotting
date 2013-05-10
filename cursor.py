import math
import operator

class Cursor(object):
    """
    A cursor object is a lot like the turtle used in the LOGO programming
    language, except it is designed for serious drawing and supports coordinate
    transforms.

    """
    __slots__ = ['pos', 'angle', '_picture', '_stack', '_units']


    def __init__(self, picture, x=0, y=0, units=None):
        self._picture = picture
        self._units = units
        self.pos = (x, y)
        self._stack = []


    def goto(self, x, y):
        """
        Move cursor to coordinate `(x, y)`, facing the direction taken to get
        there.

        """
        x0, y0 = self.pos
        self.pos = x, y
        self.angle = math.atan2(y - y0, x - x0)
        return self


    @property
    def rel(self):
        return self._picture.units(self._units, 'pt', *self.pos)


    def push(self):
        """
        Push the current point onto the stack

        """
        self._stack.append(self.rel)
        return self

    def pop(self):
        """
        Push the current point onto the stack

        """
        return self._stack.pop()


    def aim(self, x, y):
        """
        Aim in the direction of `(x, y)`, but do not move there.

        """
        x0, y0 = self.pos
        self.angle = math.atan2(y - y0, x - x0)
        return self


    def strafe(self, x, y):
        """
        Move to coordinate `(x, y)`, without changing orientation.

        """
        self.pos = x, y
        return self


    def move(self, dx=0, dy=0, d=1):
        """
        Move by `(dx, dy)` in the current coordinates.

        """
        x, y = self.pos
        self.pos = x + dx, y + dy
        return self


    def forward(self, distance):
        dx = math.cos(self.angle)
        dy = math.sin(self.angle)


    def clockwise(self, da):
        self.angle += da
        return self

    def chunits(self, units):
        """
        Change to the new unit. Will implicitly transform into the relative
        (subpicture) space, as no other space is allowed units.

        """
        self.pos = self._picture.units(self._units, units, *self.pos)
        self._units = units
        return self

    def right(self, d):
        """Move towards right edge by given units"""
        return self.move(d, 0)

    def left(self, d):
        """Move towards left edge by given units"""
        return self.move(-d, 0)

    def up(self, d):
        """Move towards top edge by given units"""
        return self.move(0, d)

    def down(self, d):
        """Move towards boddom edge by given units"""
        return self.move(0, -d)

    inches = property(operator.methodcaller('chunits', 'inches'),
                   doc='Change units to inches')
    mm = property(operator.methodcaller('chunits', 'mm'),
                  doc='Change units to millimetres')
    cm = property(operator.methodcaller('chunits', 'cm'),
                  doc='Change units to centimetres')
    pt = property(operator.methodcaller('chunits', 'pt'),
                  doc='Change units to postscript points')
    tp = property(operator.methodcaller('chunits', 'tp'),
                  doc='Change units to TeX (or printer\'s) points')

    def __repr__(self):
        return '< Cursor at (%.3g, %.3g) %s >' % (self.pos[0], self.pos[1], self._units)

