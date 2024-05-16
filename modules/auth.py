import cherrypy
from cherrypy._cperror import HTTPRedirect
import os
import time
import math
import secrets
import inspect
import json
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

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
        if c in "+-_.":
            continue
        return False
    return True

def valid_email( s ):
    acc,_,domain = s.partition("@")
    return valid_username(acc) and valid_domain(domain)

class Auth:
    def _check_password(self,pwhash,password):
        try:
            ph = PasswordHasher()
            if ph.verify(pwhash, password):
                return True
        except VerificationError:
            pass
        return False

    def _login(self,username,password):
        user = self.mdb["users"].find_one({ "username":username, "active":True })
        if user is not None and "pwhash" in user:
            if self._check_password(user["pwhash"], bytes(password,"utf-8")):
                sessid = secrets.token_hex()
                s = { "sessid":sessid }
                ph = PasswordHasher()
                if ph.check_needs_rehash(user["pwhash"]):
                    s["pwhash"] = ph.hash(bytes(password,"utf-8"))
                self.mdb["users"].update_one({"_id":user["_id"]},{"$set":s, "$unset":{"pwtoken":True, "pwtokenexp":True}})
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
        pwtoken = secrets.token_urlsafe(256)
        user = {
            "username": username,
            "email": email,
            "active": True,
            "pwtoken": pwtoken,
            "pwtokenexp": int(time.time()) + 24*60*60,
            "mails":["pwinit"],
        }
        for k,v in kwargs.items():
            if k in ["lang"]:
                user[k] = v
        self.mdb["users"].insert_one(user)
        return True

    @cherrypy.expose
    def login(self, username = None, password = None, redirectto="/"):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, password]):
            if self._login(username,password):
                raise HTTPRedirect(redirectto)
            return self.serve_site("auth/%s" % url, url = url, state = "failed", redirectto = redirectto)
        return self.serve_site("auth/%s" % url, url = url, redirectto = redirectto)

    @cherrypy.expose
    def register(self, username = None, email = None, email_again = None, state=None, me=None, url=None, **kwargs):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, email, email_again]):
            state = self._register(username, email, email_again, **kwargs)
            if state is True:
                return self.serve_site("auth/register_next", url = url, state = state, username = username, email = email, **kwargs)
            return self.serve_site("auth/%s" % url, url = url, state = state, username = username, email = email, **kwargs)
        return self.serve_site("auth/%s" % url, url = url )

    @cherrypy.expose
    def reset_password(self, username=None, email=None ):
        url = inspect.stack()[0][3]
        if cherrypy.request.method == "POST" and all([username, email]):
            user = self.mdb["users"].find_one({ "username":username, "email":email, "active":True })
            if user:
                pwtoken = secrets.token_urlsafe(256)
                self.mdb["users"].update_one({"_id":user["_id"]},{"$set":{"pwtoken":pwtoken, "pwtokenexp":int(time.time()) + 24*60*60},"$push":{"mails":"pwreset"}})
            return self.serve_site("auth/reset_password_next", url = url )
        return self.serve_site("auth/%s" % url, url = url )

    @cherrypy.expose
    def change_password(self, old_password=None, new_password=None, new_password_again=None, redirectto="/"):
        url = inspect.stack()[0][3]
        user = self.get_user()
        state = None
        if user is not None and "pwhash" in user:
            if cherrypy.request.method == "POST" and all([old_password, new_password, new_password_again]):
                if new_password == new_password_again:
                    state = "pw_nomatch"
                elif not self._check_password(user["pwhash"], bytes(old_password,"utf-8")):
                    state = "pw_failed"
                else:
                    ph = PasswordHasher()
                    h = ph.hash(bytes(new_password,"utf-8"))
                    self.mdb["users"].update_one({"_id":user["_id"]},{"$set":{ "pwhash": h}})
                    raise HTTPRedirect(redirectto)
            return self.serve_site("auth/%s" % url, url = url, user = user, state = state, redirectto = redirectto)
        else:
            raise HTTPRedirect(redirectto)

    @cherrypy.expose
    def set_password(self, pwtoken, password=None, password_again=None, redirectto="/"):
        url = inspect.stack()[0][3]
        state = None
        if cherrypy.request.method == "POST" and all([password, password_again]):
            user = self.mdb["users"].find_one({ "pwtoken":pwtoken, "pwtokenexp":{"$gte":time.time()}, "active":True })
            if user:
                if password == password_again:
                    ph = PasswordHasher()
                    h = ph.hash(bytes(password,"utf-8"))
                    self.mdb["users"].update_one({"_id":user["_id"]},{"$set":{ "pwhash": h}, "$unset":{"pwtoken":True, "pwtokenexp":True}})
                    raise HTTPRedirect(redirectto)
                else:
                    state = "pw_nomatch"
        return self.serve_site("auth/%s" % url, url = url, pwtoken = pwtoken, state = state, redirectto = redirectto)

    @cherrypy.expose
    def logout(self,redirectto="/"):
        if "sessid" in cherrypy.request.cookie:
            sessid = cherrypy.request.cookie["sessid"].value
            self.mdb["users"].update_one({"sessid":sessid},{"$set":{"sessid":None}})
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
