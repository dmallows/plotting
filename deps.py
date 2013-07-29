# A "lazy" dependency manager -- only loads dependencies as they are __needed__.
# Cuts down on initialisation time.

# We make use of partial functions, because they were probably designed for such
# things!

# This also affords a *nice* way to do configuration. We just set a new handler!

from functools import partial
from weakref import ref

class LazyDependencyManager(object):
    def __init__(self):
        self._dependencies = {}
        self._handlers = {}

    def provide(self, dep, handler, *args, **kwargs):
        if dep in self._handlers:
            raise RuntimeError(
                'Dependencies cannot be changed once provided')
        self._dependencies[dep] = partial(handler, *args, **kwargs)

    def get(self, dep):
        got = self._handlers.get(dep)
        got = (got and got()) or self._dependencies[dep]()
        self._handlers[dep] = ref(got)
        return got

    def require(self, **kx):
        that = self
        def f2(f):
            def f3(*args, **kwargs):
                new_kwargs = dict((k, self.get(v)) for k, v in kx.items())
                new_kwargs.update(kwargs)
                return f(*args, **new_kwargs)
            return f3
        return f2

depman = LazyDependencyManager()
