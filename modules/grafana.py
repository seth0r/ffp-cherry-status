import cherrypy
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import os
import requests

class Grafana:
    @cherrypy.expose
    def grafana_login(self):
        user = self.get_user()
        if not user:
            raise HTTPRedirect("/login?redirectto=/grafana/login")
        headers = {}
        for k,v in cherrypy.request.headers.items():
            headers[k] = v
        headers.update({
            "X-WEBAUTH-USER":user["username"],
            "X-WEBAUTH-EMAIL":user["email"],
        })
        r = requests.get("http://grafana:3000/grafana/login", headers = headers, allow_redirects=False)
        cherrypy.response.status = r.status_code
        for k,v in r.headers.items():
            if k not in ["Set-Cookie"]:
                cherrypy.response.headers[k] = v
        cookie = cherrypy.response.cookie
        for c in r.cookies:
            cookie[ c.name ] = c.value
            cookie[ c.name ]['version'] = c.version
            cookie[ c.name ]['expires'] = c.expires
            if c.path_specified:
                cookie[ c.name ]['path'] = c.path
        return r.content

    @cherrypy.expose
    def grafana_logout(self):
        headers = {}
        for k,v in cherrypy.request.headers.items():
            headers[k] = v
        r = requests.get("http://grafana:3000/grafana/logout", headers = headers, allow_redirects=False)
        cherrypy.response.status = r.status_code
        for k,v in r.headers.items():
            if k not in ["Set-Cookie"]:
                cherrypy.response.headers[k] = v
        cherrypy.response.headers['Location'] = "/grafana/"
        cookie = cherrypy.response.cookie
        for c in r.cookies:
            cookie[ c.name ] = c.value
            cookie[ c.name ]['version'] = c.version
            cookie[ c.name ]['expires'] = c.expires
            if c.path_specified:
                cookie[ c.name ]['path'] = c.path
        return r.content

