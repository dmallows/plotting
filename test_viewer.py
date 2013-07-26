from core import Picture

p = p0 = Picture()

p.shift(100, 100).rotate(45).tex(r'This is {\TeX} and it handles things okay $3 \times 2$')
p.fill()

print p
print p0
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
