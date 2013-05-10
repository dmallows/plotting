# Before 2.6, we had mp by a different name
import multiprocessing as mp
import Queue


def run_gui(queue):
    import gtk_viewer
    import gobject
    import threading

    gobject.threads_init()

    viewer = gtk_viewer.GtkViewer(queue.get())

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
            self.process = mp.Process(target=run_gui, args=(self.queue,))
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
