import cherrypy
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import os
import random
import json

class NodeMap:
    def node2gjs(self,node):
        if "location" not in node and "location_guess" in node:
            node["location"] = node["location_guess"]
        if "location" not in node:
            random.seed(node["_id"])
            node["location"] = [
                float(os.getenv("DEFLON","0")) - 0.001 + random.random() * 0.002,
                float(os.getenv("DEFLAT","0")) - 0.001 + random.random() * 0.002,
            ]
        f = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": node["location"],
            },
            "properties": {
                "node_id": node["_id"],
                "popup": self.get_tpl( "map/node_popup.html" ).render( node = node ),
                "info":  self.get_tpl( "map/node_info.html"  ).render( node = node ),
            }
        }
        vpn = node.get("network",{}).get("mesh_vpn",{})
        f["properties"]["uplink"] = vpn.get("enabled",False) and len(vpn.get("peers",[])) > 0
        for a in ["host","offline","offline_limits"]:
            f["properties"][a] = node[a]
        return f

    @cherrypy.expose
    def nodes_geojson(self):
        gjs = { "type": "FeatureCollection","features": [] }
        
        nodes = self.mdb["nodes"].find( {}, sort = [("last_ts",-1)] )
        for n in nodes:
            for i in [n["_id"],""]:
                ns = self.mdb["node_settings"].find_one({"_id":i})
                if ns is not None:
                    ns.pop("_id",None)
                    n.update(ns)
                    break
            gjs["features"].append( self.node2gjs(n) )

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")
