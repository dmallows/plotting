from deps import depman
from cairobackend import CairoBackend
from tex import TexDaemon
from picture import Picture
from _freetype import TextRenderer

depman.provide('backend', CairoBackend)
depman.provide('texdaemon', TexDaemon)
depman.provide('defaultpicture', Picture)
depman.provide('textrenderer', TextRenderer)
