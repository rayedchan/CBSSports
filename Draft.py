import requests
import json
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint
from bson.son import SON
from Player import Player

# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection.sports

# curl -X GET 'http://api.cbssports.com/fantasy/sports?version=3.0&response_format=JSON'

# API end point
url = "http://api.cbssports.com/fantasy/sports?version=3.0"

# Set response to return data in JSON format
params = {'response_format': 'JSON'}

# GET request call
req = requests.get(url, params)

# JSON data
data = req.json()

# Print
print(req.status_code)
print(req.json())
print()

# TODO: Find better way to handle json data
for sport in data['body']['sports']:
    print(sport)
    sport_name = sport['name']
    pro_label = sport['pro_abbrev']
    id = sport['id']



# curl "http://api.cbssports.com/fantasy/players/list?version=3.0&SPORT=baseball&response_format=JSON"
players_url="http://api.cbssports.com/fantasy/players/list?version=3.0"
sport = 'baseball'
players_params = {'response_format' : 'JSON', 'SPORT' : sport}
players_req = requests.get(players_url, players_params)
players_data = players_req.json()['body']['players']

print(players_req.json())

for player in players_data:
    id = player['id']
    firstname = player['firstname']
    lastname = player['lastname']
    position = player['position']
    age = ""

    # Check if field key exists
    if 'age' in player:
        age = player['age']
    else:
        age = ""

    '''
    print(id)
    print(firstname)
    print(lastname)
    print(position)
    print(age)
    print()
    '''

    obj = Player(id, firstname, lastname, position, age)
    obj.displayPlayer()

    dictionary = obj.__dict__
    print(dictionary)
    db.baseball.insert_one(
       dictionary
    )
    break


# Query collection with filter
cursor = db.inventory.find({})

'''
# iterate results
for doc in cursor:
     pprint(doc)

'''

'''
# insert document into collection
db.inventory.insert_one(
    {
        "item": "laptop",
        "qty": 100,
        "tags": ["machine", "code"],
        "size": {"h": 22, "w": 10, "uom": "in"}
    }
)
'''

# Subdocument key order matters in a few of these examples so we have
# to use bson.son.SON instead of a Python dict.
'''
db.inventory.insert_many([
    {"item": "journal",
     "qty": 25,
     "size": SON([("h", 14), ("w", 21), ("uom", "cm")]),
     "status": "A"},
    {"item": "notebook",
     "qty": 50,
     "size": SON([("h", 8.5), ("w", 11), ("uom", "in")]),
     "status": "A"}
])
'''



'''
cursor = db.inventory.find({"item": "journal"})
cursor = db.inventory.find({"size.h" : 7})
for inventory in cursor:
    pprint(inventory)
'''

'''
db.inventory.update_one(
    {"item": "paper"},
    {"$set": {"size.uom": "cm", "status": "F"},
     "$currentDate": {"lastModified": True}})

db.inventory.update_many(
    {"qty": {"$lt": 50}},
    {"$set": {"size.uom": "in", "status": "P"},
     "$currentDate": {"lastModified": True}})
'''

'''
db.inventory.delete_one({"status": "D"})
db.inventory.delete_many({"status": "A"})
'''

