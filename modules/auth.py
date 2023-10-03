import cherrypy
from cherrypy._cperror import HTTPRedirect
import os
import time
import math
import secrets
import hashlib
import inspect
import json

def valid_domain( s ):
    dot = s.find(".")
    if dot < 1 or dot > len(s) - 3:
        return False
    for c in s:
        if c.isascii() and c.isalnum():
            continue
        if c in "-.":
            continue
        return False
    return True

def valid_username( s ):
    if len(s) == 0:
        return False
    if s.isascii() and s.isalnum():
        return True
    for c in s:
        if c.isascii() and c.isalnum():
            continue
        if c in "-_.":
            continue
        return False
    return True

def valid_email( s ):
    acc,_,domain = s.partition("@")
    return valid_username(acc) and valid_domain(domain)

class Auth:
    def _login(self,username,password):
        user = self.mdb["users"].find_one({ "username":username, "active":True })
        if user is not None and "pwhash" in user and "pwsalt" in user:
            h = hashlib.sha256(user["pwsalt"])
            h.update(bytes(password,"utf-8"))
            if h.digest() == user["pwhash"]:
                sessid = secrets.token_hex()
                self.mdb["users"].update({"_id":user["_id"]},{"$set":{"sessid":sessid}, "$unset":{"pwtoken":True, "pwtokenexp":True}})
                cookie = cherrypy.response.cookie
                cookie['sessid'] = sessid
                cookie['sessid']['path'] = '/'
                cookie['sessid']['max-age'] = 24*60*60
                cookie['sessid']['version'] = 1
                return True
        return False

    def _register(self,username,email,email_again, **kwargs):
        if len(username) < 3:
            return "username_to_short"
        if not valid_username(username):
            return "username_invalid"
        if email != email_again:
            return "email_nomatch"
        if not valid_email(email):
            return "email_invalid"
        if self.mdb["users"].find_one({ "username":username }):
            return "exists"
        if self.mdb["users"].find_one({ "email":email }):
            return "exists"
        pwtoken = secrets.token_urlsave(256)
        user = {
            "username": username,
            "email": email,
            "active": True,
            "pwtoken": pwtoken,
            "pwtokenexp": int(time.time()) + 24*60*60,
            "mails":["pwinit"],
        }
        for k,v in kwargs:
            if k in ["lang"]:
                user[k] = v
        self.mdb["users"].insert(user)
        return True

    @cherrypy.expose
    def login(self, username = None, password = None, redirectto="/"):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, password]):
            if self._login(username,password):
                raise HTTPRedirect(redirectto)
            return self.serve_site(url, url = url, state = "failed", redirectto = redirectto)
        return self.serve_site(url, url = url, redirectto = redirectto)

    @cherrypy.expose
    def register(self, username = None, email = None, email_again = None, redirectto="/", state=None, me=None, **kwargs):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, email, email_again]):
            state = self._register(username, email, email_again, **kwargs)
            if state is True:
                raise HTTPRedirect(redirectto)
            return self.serve_site(url, url = url, state = state, username = username, email = email, redirectto = redirectto, **kwargs)
        return self.serve_site(url, url = url,  redirectto = redirectto)

    @cherrypy.expose
    def reset_password(self, username=None, email=None, redirectto="/"):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, email]):
            user = self.mdb["users"].find_one({ "username":username, "email":email, "active":True })
            if user:
                pwtoken = secrets.token_urlsave(256)
                self.mdb["users"].update({"_id":user["_id"]},{"$set":{"pwtoken":pwtoken, "pwtokenexp":int(time.time()) + 24*60*60},"$push":{"mails":"pwreset"}})
            raise HTTPRedirect(redirectto)
        return self.serve_site(url, url = url, redirectto = redirectto)

    @cherrypy.expose
    def set_password(self, pwtoken, password=None, password_again=None, redirectto="/"):
        url = inspect.stack()[0][3]
        state = None
        if cherrypy.request.method == "POST" and all([password, password_again]):
            user = self.mdb["users"].find_one({ "pwtoken":pwtoken, "pwtokenexp":{"$gte":time.time()}, "active":True })
            if user:
                if password == password_again:
                    pwsalt = secrets.token_bytes()
                    h = hashlib.sha256(pwsalt)
                    h.update(bytes(password,"utf-8"))
                    self.mdb["users"].update({"_id":user["_id"]},{"$set":{"pwsalt":pwsalt, "pwhash": h.digest()}, "$unset":{"pwtoken":True, "pwtokenexp":True}})
                    raise HTTPRedirect(redirectto)
                else:
                    state = "pw_nomatch"
        return self.serve_site(url, url = url, pwtoken = pwtoken, state = state, redirectto = redirectto)

    @cherrypy.expose
    def logout(self,redirectto="/"):
        if "sessid" in cherrypy.request.cookie:
            sessid = cherrypy.request.cookie["sessid"].value
            self.mdb["users"].update({"sessid":sessid},{"$set":{"sessid":None}})
            cookie = cherrypy.response.cookie
            cookie['sessid'] = ""
            cookie['sessid']['path'] = '/'
            cookie['sessid']['max-age'] = 0
            cookie['sessid']['version'] = 1
        raise HTTPRedirect(redirectto)

    def get_user(self):
        if "sessid" in cherrypy.request.cookie:
            sessid = cherrypy.request.cookie["sessid"].value
            user = self.mdb["users"].find_one({"sessid":sessid})
            if user is not None:
                cookie = cherrypy.response.cookie
                cookie['sessid'] = sessid
                cookie['sessid']['path'] = '/'
                cookie['sessid']['max-age'] = 24*60*60
                cookie['sessid']['version'] = 1
                return user
        return None
