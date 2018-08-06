import requests
import json
import math
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint
from bson.son import SON
from Player import Player
from flask import Flask
from flask_restful import Api, Resource, reqparse

postAvgAgeCollectionName = 'positionAvgAge'

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
    #print(req.status_code)
    #print(req.json())

    return data

"""
Create database collection for each type of sport
Also, create collection to store average age for every position
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
        if id not in existingCollections:
            db.create_collection(id)
            print(id, 'collection created.')
        else:
            print(id, 'collection already exists in database.')

    # Create a separate collection for storing position average age
    if postAvgAgeCollectionName not in existingCollections:
        db.create_collection(postAvgAgeCollectionName)
        print(postAvgAgeCollectionName, 'collection created.')
    else:
        print(postAvgAgeCollectionName, 'collection already exists in database.')

"""
Given a type of sport, insert player into proper sport collection
curl "http://api.cbssports.com/fantasy/players/list?version=3.0&SPORT=baseball&response_format=JSON"
"""
def bulkInsertPlayers(db,sportId):
    players_url="http://api.cbssports.com/fantasy/players/list?version=3.0"
    players_params = {'response_format' : 'JSON', 'SPORT' : sportId}
    players_req = requests.get(players_url, players_params)
    players_data = players_req.json()['body']['players']
    #print(players_req.json())

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
        #obj.displayPlayer()

        dictionary = obj.__dict__
        #print(dictionary)

        # TODO: Adjust for bulk insert to reduce number of db calls
        # Inserts dictionary object into collection with generated _id and no unique field identified
        #db[sportId].upinsert_one(dictionary)

        # Updates the document if it exists else insert new document
        # Search filter uses id to find existing document
        db[sportId].update_one({"id" : id}, {"$set": dictionary}, upsert=True)


'''
Calculate the average age for each position for a specific sport
via MongoDB aggregate function 
'''
def getAllAvgPositionAge(db, collectionName):
    result = []
    aggre_string = [{"$group": {"_id" :"$position", "avg_age": {"$avg": "$age"}}}]
    positions = db[collectionName].aggregate(aggre_string)
    for position in positions:
        #pprint(position)
        obj={}
        obj['sport_type'] = collectionName
        obj['position'] = position['_id']
        obj['avg_age'] = position['avg_age']
        result.append(obj)

    return result
'''
Setup the average ave position collection which stores average age per position
for all sports
'''
def setupAvgPositionCollection(db, sportsJSON):
    # Clear out average collection
    db[postAvgAgeCollectionName].delete_many({})

    # Bulk insert average age positions per sport
    for sport in sportsJSON['body']['sports']:
        sportType = sport['id']
        result = getAllAvgPositionAge(db, sportType)
        db[postAvgAgeCollectionName].insert_many(result)

'''
Setup the backend layer
1. Setup the sport collections with sport players documents added
2. Setup a average collection containing average avg per position for all sports
'''
def initializeBackend(db):
    # Sports JSON data
    sportsJSON = getAllSports()

    # Create collections
    createSportsCollections(db, sportsJSON)

    for sport in sportsJSON['body']['sports']:
        #print(sport)
        sportId = sport['id']
        bulkInsertPlayers(db, sportId)

    # Sports JSON data
    sportsJSON = getAllSports()
    setupAvgPositionCollection(db, sportsJSON)

'''
Get the average age for a specific position from average avg collection
'''
def getAvgPositionAge(db, collectionName, position):
    # Query to match against a specific position and calculate age average
    # aggre_string = [{"$match": {"position": position} },{"$group": {"_id" :"$position", "avg_age": {"$avg": "$age"}}}]
    # cursor = db[collectionName].aggregate(aggre_string)
    cursor = db[postAvgAgeCollectionName].find({"sport_type": collectionName, "position": position})
    avg_age = cursor.next()['avg_age']
    return avg_age

'''
Calculates name brief of a player given first name, last name, and the type of sport
'''
def deriveNameBrief(firstName, lastName, sportType):
    name_brief = ''

    # Return empty string if either first or last names is empty
    if not firstName or not lastName:
        return ''

    # For baseball players it should be just first initial and last initial like G. S.
    if sportType == 'baseball':
        # ternary operator <firstVal> if <condition> else <useSecondVal>
        # empty string is falsy
        name_brief = firstName[0] if firstName else '' + '. ' + lastName[0] + '.'

    # For basketball players it should be first name plus last initial like Kevin D.
    elif sportType == 'basketball':
        name_brief = firstName + ' ' + lastName[0] if lastName else '' + '.'

    # For football players it should be first initial and their last name like M. Stafford
    elif sportType == 'football':
        name_brief = firstName[0] if firstName else '' + '. ' + lastName

    return name_brief

'''
Get a single player JSON object with the 
following fields returned:
{
    id:
    name_brief:
    first_name:
    last_name:
    position:
    age:
    average_position_age_diff:
}
'''
def getPlayer(db, sportType, playerId):
    player = None

    # Query using player id as a filter
    # Also exclude the generated MongoDB _id field from result
    cursor = db[sportType].find({"id" : playerId},  {"_id": 0})

    # Get number of documents from query
    num = cursor.count()
    print(num)

    # There exist 1 document from query
    if num != 0:
        # Get first document in cursor
        player = cursor.next()

        # Add the calculated fields to JSON object
        player["name_brief"] = deriveNameBrief(player['first_name'], player['last_name'], sportType)
        #TODO: Update code to get player average
        player["average_position_age_diff"] = getAvgPositionAge(db, sportType, player['position']) - player['age']
        print(player)

    return player

'''
Get all the players in a given sport
'''
def getAllPlayers(db, sportName):
    playerList = []

    # Query all documents in a given sport collection
    # excluding the generated id
    cursor = db[sportName].find({}, {"_id": 0})

    # Add each player with calculated fields to list
    for player in cursor:
        # Calculate custom fields
        player["name_brief"] = deriveNameBrief(player['first_name'], player['last_name'], sportName)

        # Check if player age exists
        if player['age']:
            player["average_position_age_diff"] = getAvgPositionAge(db, sportName, player['position']) - player['age']

        # Insert to front of list
        playerList.insert(0, player)

    return playerList


# Current Average = CA
# Current Total Players = CTP
# New Player Age = NPA
# Player Age = PA
# Old Player Age = OPA
# New Player Age = NPA

# New AVG on insert of new player = ((CA * CTP) + NPA) / (CTP + 1)
# New AVG on deletion of player = ((CA * CTP)  - PA / (CTP - 1)
# New AVG on update of player age = (CA * CTP) - OPA + NA / CTP

# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection.sports

#initializeBackend(db)

# Use Flask Framework to create REST endpoint
app = Flask(__name__)
api = Api(app)

class SportPlayer(Resource):
    # Get a single sport player
    # curl http://127.0.0.1:5000/user/baseball/2165933
    def get(self, sportType, playerId):
        player = getPlayer(db, sportType, playerId)

        if player is None:
            return "User not found", 404

        return player, 200

# Define URI endpoints
api.add_resource(SportPlayer, "/user/<string:sportType>/<string:playerId>")

@app.route('/sports/<sportName>')
def getAllSportPlayers(sportName):
    playerList = getAllPlayers(db, sportName)
    return json.dumps({'results': playerList}), 200

# Debug mode, enables reload automatically
app.run(debug =True)


#results = getAllAvgPositionAge(db, "baseball")
#print(results)

#x = getAvgPositionAge(db, "baseball", "LF")
#print(x)

'''
x = deriveNameBrief('Derek', 'Jeter', 'baseball')
print(x)
x = deriveNameBrief('Kevin', 'Durant', 'basketball')
print(x)
x = deriveNameBrief('Matt', 'Stafford', 'football')
print(x)
'''

'''
getPlayer(db, "baseball", "2226042")
'''

'''
# Query collection with filter
cursor = db.inventory.find({})
'''

#results = getAllAvgPositionAge(db, "baseball")
#print(results)


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

