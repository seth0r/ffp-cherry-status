import logging
import cherrypy
import atexit

logging.basicConfig(level=logging.WARNING)

cherrypy.config.update({
    'environment': 'embedded',
})

from root import Root

class App(Root):
    def __init__(self):
        self.logger = logging.getLogger( self.__class__.__name__ )
        for cls in self.__class__.__mro__:
            self.logger.info("Loaded class %s." % cls)
            if cls is not self.__class__ and hasattr(cls,"__init__"):
                getattr(cls,"__init__")(self)
        
    @cherrypy.expose
    def cherry_health_check(self):
        return "success"

if __name__ == '__main__':
    cherrypy.config.update({'server.socket_host': '::','server.socket_port':8000})
    cherrypy.quickstart( App() )
else:
    application = cherrypy.Application( App( ) , script_name=None, config=None)
    cherrypy.config.update({'engine.autoreload.on': False})
    cherrypy.server.unsubscribe()
    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()
    atexit.register(cherrypy.engine.stop)
