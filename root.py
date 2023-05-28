import cherrypy
from cherrypy import HTTPError
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import jinja2
from pymongo import MongoClient
import os

import modules

class Root( * modules.__classes__.values() ):
    def __init__(self):
        self.mdbe = MongoClient( os.getenv( "MONGODB_URI","mongodb://localhost/" ), connect = False )
        self.mdb = self.mdbe[ os.getenv("MONGODB_DB") ]

        self.tpldir = os.path.join( os.path.dirname(os.path.realpath(__file__) ),"tpl")
        self.tplenv = jinja2.Environment( 
            loader = jinja2.FileSystemLoader( self.tpldir ),
            trim_blocks = True,
            lstrip_blocks = True
        )
        
    def get_tpl(self, *args):
        for t in args:
            try:
                return self.tplenv.get_template( t )
            except jinja2.exceptions.TemplateNotFound:
                pass

    def serve_site(self, tpl, **kwargs):
        tpl = self.get_tpl( tpl, "%s.html" % tpl )
        if tpl is not None:
            return tpl.render( me = self, **kwargs )
        raise HTTPError(404,"Template not found.")

    @cherrypy.expose
    def default(self,name):
        return self.serve_site( name )

