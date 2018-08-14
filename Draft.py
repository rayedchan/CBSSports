import requests
import json
import math
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint
from bson.son import SON
from Player import Player
from flask import Flask, jsonify, make_response, abort, request
from flask_restful import Api, Resource, reqparse
from bson.json_util import dumps
from mongotriggers import MongoTrigger

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
        name_brief = (firstName[0] if firstName else '') + '. ' + lastName[0] + '.'

    # For basketball players it should be first name plus last initial like Kevin D.
    elif sportType == 'basketball':
        name_brief = (firstName + ' ' + lastName[0] if lastName else '') + '.'

    # For football players it should be first initial and their last name like M. Stafford
    elif sportType == 'football':
        name_brief = (firstName[0] if firstName else '') + '. ' + lastName

    # All other sports
    else:
        name_brief = firstName + ' ' + lastName

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
    #num = cursor.count() deprecated
    num = db[sportType].count_documents({"id" : playerId})
    print(num)

    # There exist 1 document from query
    if num != 0:
        # Get first document in cursor
        player = cursor.next()

        # Add the calculated fields to JSON object
        player["name_brief"] = deriveNameBrief(player['first_name'], player['last_name'], sportType)
        #TODO: Update code to get player average

        # Check if player age exists
        if player['age']:
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
def updateAgeAvgOnInsert(db, sportType, newPlayer):
    position = newPlayer['position']
    print(position)

    # Get total number of documents for specific position with valid age
    currentTotalPlayer = db[sportType].count_documents({"position": position, "age": {"$gt": 0}})
    print('Total players ', currentTotalPlayer)

    # Get current average for position
    avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": position})
    currentAverage = 0
    # Iterate results
    for doc in avgCursor:
        pprint(doc)
        currentAverage = doc['avg_age']

    newPlayerAge = newPlayer['age']
    if newPlayerAge > 0:
        newPositionAvg = ((currentAverage * currentTotalPlayer) + newPlayerAge) / (currentTotalPlayer + 1)
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position}, {"$set": {"avg_age": newPositionAvg}}, upsert=True)
    else:
        print('No updates to position age average')

def updateAgeAvgOnDelete(db, sportType, rmPlayer):
    position = rmPlayer['position']
    print(position)

    # Get total number of documents for specific position with valid age
    currentTotalPlayer = db[sportType].count_documents({"position": position, "age": {"$gt": 0}})
    print('Total players ', currentTotalPlayer)

    # Get current average for position
    avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": position})
    currentAverage = 0
    # Iterate results
    for doc in avgCursor:
        pprint(doc)
        currentAverage = doc['avg_age']

    rmPlayerAge = rmPlayer['age']
    if rmPlayerAge > 0:
        newTotalPlayer = currentTotalPlayer - 1
        newPositionAvg = 0
        if newTotalPlayer != 0:
            newPositionAvg = ((currentAverage * currentTotalPlayer) - rmPlayerAge) / (currentTotalPlayer - 1)
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position}, {"$set": {"avg_age": newPositionAvg}}, upsert=True)
    else:
        print('No updates to position age average')

def updateAgeAvgOnUpdate(db, sportType, oldPlayerState, newPlayerState):
    position = oldPlayerState['position']
    print(position)

    # Get total number of documents for specific position with valid age
    currentTotalPlayer = db[sportType].count_documents({"position": position, "age": {"$gt": 0}})
    print('Total players ', currentTotalPlayer)

    # Get current average for position
    avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": position})
    currentAverage = 0
    # Iterate results
    for doc in avgCursor:
        pprint(doc)
        currentAverage = doc['avg_age']

    oldPlayerAge = oldPlayerState['age']
    newPlayerAge = newPlayerState['age']

    # More checking e.g player switch position, player marked invalid age
    if oldPlayerAge > 0 and newPlayerAge > 0:
        newPositionAvg = ((currentAverage * currentTotalPlayer) - oldPlayerAge + newPlayerAge) / currentTotalPlayer
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position}, {"$set": {"avg_age": newPositionAvg}}, upsert=True)
    else:
        print('No updates to position age average')

'''
Function to trigger on update of a collection in MongoDB
Post operation event
op_document - document that is updated
'''
def notify_manager(op_document):
    print('wake up! someone is adding me money')
    print(op_document)

    totalDocs = db['soccer'].count_documents({})
    print('Total documents ', totalDocs)

# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection.sports

#initializeBackend(db)

# Use Flask Framework to create REST endpoint
app = Flask(__name__)
api = Api(app)

# Test method
@app.route('/test', methods=['GET'])
def test():
    # Connection must have oplog enable
    # Start mongod with option --replSet rs and then execute rs.initiate() in mongo shell
    triggers = MongoTrigger(connection)

    # listens to update/insert/delete, any of these will trigger the callback
    triggers.register_insert_trigger(notify_manager,'sports', 'soccer')  # register_op_trigger(func, db_name=None, collection_name=None)
    triggers.tail_oplog()

    print('test')
    # make an operation to simulate interaction
    connection['sports']['soccer'].insert_one({"balance": 1000})
    #triggers.stop_tail()
    return "hello"

class SportPlayer(Resource):
    # Get a single sport player
    # curl http://127.0.0.1:5000/baseball/player/2165933
    def get(self, sportType, playerId):
        player = getPlayer(db, sportType, playerId)

        if player is None:
            abort(404)  # 404 Resource Not Found

        return jsonify({"player": player}), 200

    # Create a new player
    # curl -i -H "Content-Type: application/json" -X POST -d '{"age": 35, "first_name":"Satoshi", "last_name":"Ketchum", "position":"C"}' http://localhost:5000/baseball/player/5000001
    # curl -i -H "Content-Type: application/json" -X POST -d '{"age": 31, "first_name":"Lionel", "last_name":"Messi", "position":"F"}' http://localhost:5000/soccer/player/1
    # curl -i -H "Content-Type: application/json" -X POST -d '{"age": 33, "first_name":"Cristiano", "last_name":"Ronaldo", "position":"F"}' http://localhost:5000/soccer/player/2
    # curl -i -H "Content-Type: application/json" -X POST -d '{"age": 27, "first_name":"Antoine", "last_name":"Griezmann", "position":"F"}' http://localhost:5000/soccer/player/3
    def post(self,sportType, playerId):
        # Check if the player id exists in the backend
        player = getPlayer(db, sportType, playerId)

        # Create new player if id does not exist
        if player is None:
            newPlayer ={
                'id' : playerId,
                'age' : request.json['age'],
                'first_name': request.json['first_name'],
                'last_name': request.json['last_name'],
                'position': request.json['position']
            }

            # Update average age position collection
            updateAgeAvgOnInsert(db, sportType, newPlayer)

            # Insert player to sport collection
            db[sportType].insert_one(newPlayer)
            del newPlayer['_id']  # Remove MongoDB generated Object Id

            return jsonify({"player": newPlayer})  # 201 Created
            #return dumps(newPlayer), 200
        else:
            return make_response(jsonify({'error': 'User already exists'}), 400)  # Bad Request

    # Delete a player
    # curl -i -H "Content-Type: application/json" -X DELETE http://localhost:5000/baseball/player/5000001
    # curl -i -H "Content-Type: application/json" -X DELETE http://localhost:5000/soccer/player/2
    def delete(self, sportType, playerId):
        # Check if the player id exists in the backend
        player = getPlayer(db, sportType, playerId)

        if player is None:
            return make_response(jsonify({'error': 'User does not exist'}), 404)  # Not Found
        else:
            # Update avg position age
            updateAgeAvgOnDelete(db, sportType, player)
            # Delete document from db
            db[sportType].delete_one({'id': playerId})
            return {}, 204  # No content

    # Update a player
    # curl -i -H "Content-Type: application/json" -X PUT -d '{"age": 35, "first_name":"Satoshi", "last_name":"Reddo", "position":"CF"}' http://localhost:5000/baseball/player/5000001
    # curl -i -H "Content-Type: application/json" -X PUT -d '{"age": 50, "first_name":"Cristiano", "last_name":"Ronaldo", "position":"F"}' http://localhost:5000/soccer/player/2
    def put(self, sportType, playerId):
        # Check if the player id exists in the backend
        player = getPlayer(db, sportType, playerId)

        if player is None:
            return make_response(jsonify({'error': 'User does not exist'}), 404)  # Not Found
        else:
            updatePlayer ={
                'age' : request.json['age'],
                'first_name': request.json['first_name'],
                'last_name': request.json['last_name'],
                'position': request.json['position']
            }

            # Update avg position age
            updateAgeAvgOnUpdate(db, sportType, player, updatePlayer)
            # Update document in db
            db[sportType].update_one({"id": playerId}, {"$set": updatePlayer}, upsert=False)
            return {}, 200  # No content


# Define URI endpoints
api.add_resource(SportPlayer, "/<string:sportType>/player/<string:playerId>")

@app.route('/sports/<string:sportName>/players', methods=['GET'])
def getAllSportPlayers(sportName):
    playerList = getAllPlayers(db, sportName)
    # return formatted JSON
    return jsonify({'players': playerList}), 200
    # return compressed json
    #return json.dumps({'results': playerList}), 200

# Get all types of sports
@app.route('/sports', methods=['GET'])
def getAllSportTypes():
     # Get all collections within a database
     sportList = db.list_collection_names()

     # Remove average collection from list
     sportList.remove(postAvgAgeCollectionName)
     #pprint(sportList)

     return jsonify({"sports": sportList}), 200

# Get a specific sport
@app.route('/sports/<string:sportType>', methods=['GET'])
def getSportType(sportType):
    # Get all collections within a database
    sportList = db.list_collection_names()

    for sportName in sportList:
        if sportName == sportType:
            return jsonify({'sport': sportName}), 200

    abort(404)

# Create a new sport collection
# curl -i -H "Content-Type: application/json" -X POST -d '{"sport_type":"soccer"}' http://localhost:5000/sports
@app.route('/sports', methods=['POST'])
def createSport():
    if not request.json or not 'sport_type' in request.json:
        abort(400) # 400 Bad request
    db.create_collection(request.json['sport_type'])
    return jsonify({'sport': request.json['sport_type']}), 201 # 201 Created

# Delete a sport
# curl -i -H "Content-Type: application/json" -X DELETE http://localhost:5000/sports/soccer
@app.route('/sports/<string:sportType>', methods=['DELETE'])
def deleteSport(sportType):
    # Get all collections within a database
    sportList = db.list_collection_names()

    # Find the sport and remove
    for sportName in sportList:
        if sportName == sportType:
            db.drop_collection(sportType)
            return jsonify({'result': True})

    abort(404)


# Response error for 404 in JSON
@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

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

