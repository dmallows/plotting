from core import Picture
from deps import depman
import random

p = p0 = Picture()


t = p.shift(100, 100)
for i in xrange(10):
    t.shift(random.randrange(100),
            random.randrange(100)).\
            shift(-100, 0).\
            tex(r'Hello World! 01745 88127')
#p.fill()

#tex = depman.get('texdaemon')
#tex.page(r'$3 \times 2$')

#print p
#print p0
p0.save('test.pdf')
# This is a job for freetype?!
#p = picture.Picture()

#t = TexDaemon()

#print t.page('foo')
#p.linewidth(0.5).linejoin('round').linecap('round')
#p.rectangle(0, 0, 10, 10).stroke()
#p.line_to(20, 20).line_to(20,10).line_to(100, 100).stroke()

#1 / 0

#v = gtk_viewer.GtkViewer(p)
#v.run()
