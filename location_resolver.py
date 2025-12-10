# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, math
from typing import Optional, Tuple, Dict, Any

FALLBACK=[
  {"name":"Київ","region":"м. Київ","lat":50.4501,"lon":30.5234},
  {"name":"Львів","region":"Львівська область","lat":49.8397,"lon":24.0297},
  {"name":"Свалява","region":"Закарпатська область","lat":48.5482,"lon":22.9856},
  {"name":"Харків","region":"Харківська область","lat":49.9935,"lon":36.2304},
  {"name":"Одеса","region":"Одеська область","lat":46.4825,"lon":30.7233},
]

def _hav(a,b):
    R=6371.0
    lat1,lon1=map(math.radians,a)
    lat2,lon2=map(math.radians,b)
    dlat=lat2-lat1; dlon=lon2-lon1
    x=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(x))

def _load():
    p=os.path.join(os.path.dirname(__file__),"backend","settlements.json")
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:
                j=json.load(f)
                if isinstance(j,list): return j
        except Exception:
            pass
    return []

def _local(name,coord):
    db=_load() or FALLBACK
    if name:
        n=name.strip().lower()
        cand=[r for r in db if r.get("name","").strip().lower()==n]
        if cand:
            if coord and any("lat" in r and "lon" in r for r in cand):
                best=min(cand, key=lambda r:_hav(coord,(float(r.get("lat",0)),float(r.get("lon",0)))) if r.get("lat") is not None else 1e9)
                return best
            return cand[0]
    if coord:
        wc=[r for r in db if "lat" in r and "lon" in r]
        if wc:
            return min(wc,key=lambda r:_hav(coord,(float(r["lat"]),float(r["lon"]))))
    return None

def _nominatim(name,coord):
    try:
        from geopy.geocoders import Nominatim
        g=Nominatim(user_agent="uk_blackout_bot")
        loc=None
        if coord:
            loc=g.reverse(f"{coord[0]}, {coord[1]}", language="uk")
        elif name:
            loc=g.geocode(f"{name}, Україна", language="uk")
        if not loc: return None
        raw=loc.raw or {}
        addr=raw.get("address",{})
        region=addr.get("state") or addr.get("region") or addr.get("county") or addr.get("province") or ""
        city=addr.get("city") or addr.get("town") or addr.get("village") or name or ""
        lat=float(raw.get("lat",loc.latitude)); lon=float(raw.get("lon",loc.longitude))
        return {"name":city,"region":region,"lat":lat,"lon":lon}
    except Exception:
        return None

def resolve_region(city_name: Optional[str]=None, lat: Optional[float]=None, lon: Optional[float]=None):
    coord=(lat,lon) if (lat is not None and lon is not None) else None
    hit=_local(city_name,coord)
    if hit and hit.get("region"): 
        return {"name": hit.get("name", city_name or ""), "region": hit["region"], "lat": hit.get("lat"), "lon": hit.get("lon")}
    hit=_nominatim(city_name,coord)
    if hit and hit.get("region"): return hit
    return _local(city_name,coord)
