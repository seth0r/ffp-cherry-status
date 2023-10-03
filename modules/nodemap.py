import cherrypy
from cherrypy._cperror import HTTPRedirect
from cherrypy.lib.static import serve_fileobj, serve_file
import os
import time
import math
import random
import json

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    km = 6367 * c
    return km

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

def getkindofaddr(addr):
    KINDS = {
        0:"wired",
        1:"wireless",
        2:"unknown_2",
        3:"wired",
        4:"wired",
        5:"wireless",
        6:"unknown_6",
        7:"tunnel",
    }
    return KINDS[ int(addr[-1],16) & 7 ]

class NodeMap:
    def node2gjs(self,node):
        now = time.time()
        loc = getnodeloc(node)
        nexthop = self.mdb["nodes"].find_one({ "ifaddr":node.get("network",{}).get("nexthop",None) })
        color = ([ co[0] for co in sorted( filter(
                lambda co: node['offline'] <= co[1],
                node.get("offline_limits",{}).items()
            ), key = lambda co: co[1] )]+[None] )[0]
        lang = self.get_lang()
        f = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": loc,
            },
            "properties": {
                "type" : "node",
                "id"   : node["_id"],
                "popup": self.get_tpl( "map/node_popup.%s.html" % lang, "map/node_popup.html" ).
                    render( node = node, nexthop = nexthop, loc = loc, color = color, now = now ),
                "info" : self.get_tpl( "map/node_info.%s.html" % lang, "map/node_info.html"  ).
                    render( node = node, nexthop = nexthop, loc = loc, color = color, now = now ),
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

    def get_link_stats(self,thisnode,othernode, now):
        links = []
        for l in self.mdb["neighbours"].find({
            "local":{"$in":thisnode["ifaddr"]},
            "remote":{"$in":othernode["ifaddr"]},
            "time":{"$gte":now - 24*60*60},
            "stat.tq":{"$gt":0}
          }):
            l["stat"]["lastseen"] += now - l["time"]
            l["stat"]["kind"] = getkindofaddr( l["local"] )
            rl = self.mdb["neighbours"].find_one({ "local":l["remote"], "remote":l["local"], "time":{"$gte":now - 24*60*60}, "stat.tq":{"$gt":0} })
            if rl:
                rl["stat"]["lastseen"] += now - rl["time"]
                rl["stat"]["kind"] = getkindofaddr( rl["local"] )
            links.append((l["stat"],rl["stat"] if rl else None))
        links.sort( key = lambda x: x[0]["tq"], reverse = True )
        return links

    def get_links(self):
        now = time.time()
        alllinks = []
        for link in self.mdb["neighbours"].find( { "time":{"$gte":now - 24*60*60}, "stat.tq":{"$gt":0} }, sort = [("time",1)] ):
            thisnode = self.nodeaddsettings( self.mdb["nodes"].find_one({"ifaddr":link["local"]}) )
            othernode = self.nodeaddsettings( self.mdb["nodes"].find_one({"ifaddr":link["remote"]}) )
            if None in [thisnode,othernode]:
                continue
            ids = (thisnode["_id"],othernode["_id"])
            if ids in alllinks:
                continue
            alllinks.append(ids)
            thisloc  = getnodeloc(thisnode)
            otherloc = getnodeloc(othernode)
            stats = self.get_link_stats( thisnode, othernode, now )
            res = {
                "link_id": "%s_%s" % ids,
                "nodes": (thisnode,othernode),
                "stats": stats,
            }
            if any(map( lambda x: x[1], stats )):
                res["coordinates"] = [thisloc,[ (thisloc[0] + otherloc[0]) / 2, (thisloc[1] + otherloc[1]) / 2 ]]
            else:
                res["coordinates"] = [thisloc, otherloc]
            if thisloc[0] <= otherloc[0]:
                res["l"] = 0
                res["r"] = 1
            else:
                res["r"] = 0
                res["l"] = 1
            res["length"] = 1000 * haversine( thisloc[0],thisloc[1], otherloc[0],otherloc[1] )
            res["tq"] = stats[0][0]["tq"]
            res["otq"] = None
            res["lastseen"] = 24*60*60
            for l in stats:
                if l[1]:
                    if res["otq"] is None or l[1]["tq"] > res["otq"]:
                        res["otq"] = l[1]["tq"]
                if l[0]["lastseen"] < res["lastseen"]:
                    res["lastseen"] = l[0]["lastseen"]
            yield res

    def link2gjs(self,l):
        lang = self.get_lang()
        f = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": l["coordinates"],
            },
            "properties": {
                "type": "link",
                "id"  : l["link_id"],
                "info": self.get_tpl( "map/link_info.%s.html" % lang, "map/link_info.html"  ).render( link = l ),
                "tq"  : l["tq"] / 255,
                "seen": l["lastseen"],
            }
        }
        return f

    @cherrypy.expose
    def links_geojson(self):
        gjs = { "type": "FeatureCollection","features": [] }

        for l in self.get_links():
            gjs["features"].append( self.link2gjs( l ) )

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return bytes(json.dumps(gjs),"utf-8")
