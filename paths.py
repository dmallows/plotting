# What is a cursor? It's just a one element path!
# Cursors can have multiple points in their sequence

class Cursor(object):
    def __init__(self, default_space):
        self._commands = []
        self.goto(0, 0, default_space)

    def goto(self, x, y, space=None):
        if space is not None:
            self._commands.append(('space', space))
        self._commands.append(('go', x, y))
        return self

    def move(self, dx=0, dy=0, space=None):
        if space is not None:
            self._commands.append(('space', space))
        self._commands.append(('move', dx, dy))
        return self

    def next(self):
        self._commands.append(('next',))

    def line(self):
        self._commands.append(('line',))
        return self

    def curve(self):
        self._commands.append(('curve',))
        return self

    def cycle(self):
        self._commands.append(('cycle',))
        return self

    def ctrl(self):
        self._commands.append(('ctrl',))
        return self

    def _iter_collapse(self, spaces):
        # Collapses down to a cursor in base units
        commands = iter(self._commands)
        i = next(commands, None)
        assert i[0] == 'space'
        space = i[1]
        x = 0
        y = 0
        f, g = spaces[space]
        # Needs to 
        for i in commands:
            op = i[0]
            if op == 'go':
                x, y = i[1:]
                x1, y1 = f(x, y)
                yield ('point', x1, y1)

            elif op == 'move':
                dx, dy = i[1:]
                x += dx
                y += dy
                x1, y1 = f(x, y)
                yield ('point', x1, y1)

            elif op == 'space':
                f0 = f
                f, g = spaces[i[1]]
                x, y = g(*f0(x, y))

            else:
                yield i

    def collapse(self, spaces):
        return [list(j)[-1] for i, j in
                itertools.groupby(
                    self._iter_collapse(spaces),
                    key=operator.itemgetter(0))]

import itertools, operator
# TODO: resolve paths in different spaces

# Fictional test

#'[cm] 10,10  -- 10, 10 .. 10, 10 .. 10, 10 -- 20, 20'
# Belong to picture... so no probelems with reifying.
#p = picture.cursor().goto(10, 10)
#picture.tex('Test World', p, 'left baseline')
#picture.tex('Test World', p, 'mid mid')
# Really want to be able to do something like

# p.rotate(90).tex(r'Test text', p.cursor(100, 100, 'mm'), anchor='top left')

# This is difficult mathematics?
# Nope!

#p.tra

# Anchors

#p = Cursor('mm')
#p.goto(10, 10).curve().move(10, 0).ctrl().move().ctrl().move(-10, 0).cycle()
#
##p.move(0, 0, 'plot')
##for i in range(10000):
##    p.goto(i, i).line()
#
#
#MM2PT = 72.0 / 25.4
#PT2MM = 1.0 / MM2PT
#
#plot = lambda x, y: (x * 10, y * 10), lambda x, y: (x * 0.1, y * 0.1)
#pt = lambda x, y: (x, y), lambda x, y: (x, y)
#mm = lambda x, y: (x * MM2PT, y * MM2PT), lambda x, y: (x * PT2MM, y * PT2MM)
#
#spaces = {'mm': mm, 'pt': pt, 'plot': plot}
#
#print(p.collapse(spaces))
