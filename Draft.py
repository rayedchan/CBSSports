import requests
import json
import math
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint
from bson.son import SON
from Player import Player

"""
Get all type of sports from REST API call
curl -X GET 'http://api.cbssports.com/fantasy/sports?version=3.0&response_format=JSON'
"""
def getAllSports():
    # API end point to get all type of sports
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

    return data

"""
Create database collection for each type of sport
"""
def createSportsCollections(db, sportsJSON):
    # Get the existing collections in database
    existingCollections = db.list_collection_names()
    print("Existing collections:", existingCollections)

    # Iterate each type of sport
    for sport in sportsJSON['body']['sports']:
        print(sport)
        id = sport['id']

        # Create collection if it does not exist
        if(id not in existingCollections):
            db.create_collection(id)
            print(id, 'collection created.')
        else:
            print(id, 'collection already exists in database.')

"""
Given a type of sport, insert player into proper sport collection
curl "http://api.cbssports.com/fantasy/players/list?version=3.0&SPORT=baseball&response_format=JSON"
"""
def bulkInsertPlayers(db,sportId):
    players_url="http://api.cbssports.com/fantasy/players/list?version=3.0"
    players_params = {'response_format' : 'JSON', 'SPORT' : sportId}
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

        obj = Player(id, firstname, lastname, position, age)
        obj.displayPlayer()

        dictionary = obj.__dict__
        print(dictionary)

        # TODO: Adjust for bulk insert to reduce number of db calls

        # Inserts dictionary object into collection with generated _id and no unique field identified
        #db[sportId].upinsert_one(dictionary)

        # Updates the document if it exists else insert new document
        # Search filter uses id to find existing document
        db[sportId].update_one({"id" : id}, {"$set": dictionary}, upsert=True)


'''
Calculate the average age for each position
via MongoDB aggregate function 
'''
def getAllAvgPositionAge(db, collectionName):
    mapResult = {}
    aggre_string = [{"$group": {"_id" :"$position", "avg_age": {"$avg": "$age"}}}]
    positions = db[collectionName].aggregate(aggre_string)
    for position in positions:
        #pprint(position)
        mapResult[position['_id']] = position['avg_age']

    #print(mapResult)
    return mapResult

'''
Calculate the average age for a specific position via MongoDB aggregate function 
The remainder is truncated
'''
def getAvgPositionAge(db, collectionName, position):
    # Query to match against a specific position and calculate age average
    aggre_string = [{"$match": {"position": position} },{"$group": {"_id" :"$position", "avg_age": {"$avg": "$age"}}}]
    cursor = db[collectionName].aggregate(aggre_string)
    avg_age = cursor.next()['avg_age']
    return math.floor(avg_age)

'''
Calculates name brief of a player given first name, last name, and the type of sport
'''
def deriveNameBrief(firstName, lastName, sportType):
    name_brief = ''

    # For baseball players it should be just first initial and last initial like G. S.
    if sportType == 'baseball':
        name_brief = firstName[0] + '. ' + lastName[0] + '.'

    # For basketball players it should be first name plus last initial like Kevin D.
    elif sportType == 'basketball':
        name_brief = firstName + ' ' + lastName[0] + '.'

    # For football players it should be first initial and their last name like M. Stafford
    elif sportType == 'football':
        name_brief = firstName[0] + '. ' + lastName

    return name_brief

'''
Get a single player JSON object
'''
def getPlayer(db, sportType, playerId):
    # Query using player id as a filter
    # Also exclude the generated MongoDB _id field from result
    cursor = db[sportType].find({"id" : playerId},  {"_id": 0})

    # for player in cursor:
    #    pprint(player)

    # Get first document in cursor
    player = cursor.next()

    # Add the calculated fields to JSON object
    player["name_brief"] = deriveNameBrief(player['first_name'], player['last_name'], sportType)
    player["average_position_age_diff"] = getAvgPositionAge(db, sportType, player['position']) - player['age']
    print(player)


# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection.sports

'''
# Sports JSON data
sportsJSON = getAllSports()

# Create collections
createSportsCollections(db, sportsJSON)

for sport in sportsJSON['body']['sports']:
    print(sport)
    sportId = sport['id']
    bulkInsertPlayers(db, sportId)
    break

results = getAllAvgPositionAge(db, "baseball")
print(results)

x = getAvgPositionAge(db, "baseball", "LF")
print(x)
'''

'''
x = deriveNameBrief('Derek', 'Jeter', 'baseball')
print(x)
x = deriveNameBrief('Kevin', 'Durant', 'basketball')
print(x)
x = deriveNameBrief('Matt', 'Stafford', 'football')
print(x)
'''

getPlayer(db, "baseball", "2226042")


'''
# Query collection with filter
cursor = db.inventory.find({})
'''


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

