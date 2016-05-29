import urllib, json, os, sys
from pymongo import MongoClient
lon_min=sys.argv[2]
lat_min=sys.argv[1]
lon_max=sys.argv[4]
lat_max=sys.argv[3]
kolekcja=sys.argv[5]
adres="http://overpass.osm.rambler.ru/cgi/interpreter?data=[out:json];node[public_transport=stop_position]("+lat_min+"%2C"+lon_min+"%2C"+lat_max+"%2C"+lon_max+")%3Bout%3B"
usock = urllib.urlopen(adres)
zrodlo = usock.read()
usock.close()
try:
	gj=json.loads(zrodlo)
except ValueError:
	print "Brak danych"
obiekt=gj['elements']
client=MongoClient()
db=client.MED
collection=db[kolekcja]

for ob in obiekt:
	property=ob['tags']
	lon=ob['lon']
	lat=ob['lat']
	mongo={"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[]}}
	mongo["geometry"]["coordinates"].extend([lon, lat])
	mongo["properties"]=property
	collection.insert(mongo)

