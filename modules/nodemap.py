import cherrypy
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import os
import time
import math
import random
import json

def getnodeloc(node):
    if "location" in node:
        return node["location"]
    if "location_guess" in node:
        return node["location_guess"]
    random.seed(node["_id"])
    return [
        float(os.getenv("DEFLON","0")) - 0.001 + random.random() * 0.002,
        float(os.getenv("DEFLAT","0")) - 0.001 + random.random() * 0.002,
    ]

class NodeMap:
    def node2gjs(self,node):
        now = time.time()
        loc = getnodeloc(node)
        nexthop = self.mdb["nodes"].find_one({ "ifaddr":node.get("network",{}).get("nexthop",None) })
        color = ([ co[0] for co in sorted( filter(
                lambda co: node['offline'] <= co[1],
                node.get("offline_limits",{}).items()
            ), key = lambda co: co[1] )]+[None] )[0]
        f = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": loc,
            },
            "properties": {
                "type" : "node",
                "id"   : node["_id"],
                "popup": self.get_tpl( "map/node_popup.html" ).render( node = node, nexthop = nexthop, loc = loc, color = color, now = now ),
                "info" : self.get_tpl( "map/node_info.html"  ).render( node = node, nexthop = nexthop, loc = loc, color = color, now = now ),
            }
        }
        vpn = node.get("network",{}).get("mesh_vpn",{})
        f["properties"]["uplink"] = vpn.get("enabled",False) and len(vpn.get("peers",[])) > 0
        for a in ["host","offline","offline_limits"]:
            f["properties"][a] = node[a]
        return f

    def nodeaddsettings(self,node):
        if node is None:
            return
        for i in ["",node["_id"]]:
            ns = self.mdb["node_settings"].find_one({"_id":i})
            if ns is not None:
                ns.pop("_id",None)
                node.update(ns)
        return node

    @cherrypy.expose
    def nodes_geojson(self):
        gjs = { "type": "FeatureCollection","features": [] }
        
        for n in self.mdb["nodes"].find( {}, sort = [("last_ts",-1)] ):
            gjs["features"].append( self.node2gjs( self.nodeaddsettings(n) ) )

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")


        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")
