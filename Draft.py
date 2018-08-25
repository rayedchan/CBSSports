import requests
import json
import math
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint
from bson.son import SON
from Player import Player
from flask import Flask, jsonify, make_response, abort, request, render_template
from flask_restful import Api, Resource, reqparse
from bson.json_util import dumps
import os
from CommonUtils import getAllSports

# Name of collection to store position age averages
postAvgAgeCollectionName = 'positionAvgAge'
databaseName = os.environ.get("MONGODB_DBNAME")

# TODO: Restructure backend layer so that this won't be necessary
excludeCollections = ['system.indexes']

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

'''
Function to update position age average on insert of new document
'''
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

'''
Function to update position age average on deletion of a document
'''
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

'''
Function to update position age average on update of an existing document
'''
def updateAgeAvgOnUpdate(db, sportType, oldPlayerState, newPlayerState):
    position = oldPlayerState['position']
    newPosition = newPlayerState['position']
    currentTotalPlayer = 0
    currentAverage = 0
    npCurrentAverage = 0
    npCurrentTotalPlayer = 0

    # Empty positions
    if position is None and newPosition is None:
        print('No updates to position age average since position is invalid')
        return

    # Position are the same or old position is valid but new position is invalid
    elif position == newPosition or (position is not None and newPosition is None):
        # Get total number of documents for specific position with valid age
        currentTotalPlayer = db[sportType].count_documents({"position": position, "age": {"$gt": 0}})
        print('Total players ', currentTotalPlayer)

        # Get current average for position
        avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": position})

        # Iterate results
        for doc in avgCursor:
            pprint(doc)
            currentAverage = doc['avg_age']

    # Old position invalid and new position valid
    elif position is None and newPosition is not None:
        # Get total number of documents for specific position with valid age
        currentTotalPlayer = db[sportType].count_documents({"position": newPosition, "age": {"$gt": 0}})
        print('Total players ', currentTotalPlayer)

        # Get current average for position
        avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": newPosition})

        # Iterate results
        for doc in avgCursor:
            pprint(doc)
            currentAverage = doc['avg_age']

    # Change to different position
    else:
        # Get total number of documents for specific position with valid age
        currentTotalPlayer = db[sportType].count_documents({"position": position, "age": {"$gt": 0}})
        print('Total players ', currentTotalPlayer)

        # Get current average for position
        avgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": position})

        # Iterate results
        for doc in avgCursor:
            pprint(doc)
            currentAverage = doc['avg_age']

        # Get total number of documents for specific position with valid age
        npCurrentTotalPlayer = db[sportType].count_documents({"position": newPosition, "age": {"$gt": 0}})
        print('Total players ', npCurrentTotalPlayer)

        # Get current average for position
        npAvgCursor = db[postAvgAgeCollectionName].find({"sport_type": sportType, "position": newPosition})

        # Iterate results
        for doc in npAvgCursor:
            pprint(doc)
            npCurrentAverage = doc['avg_age']

    oldPlayerAge = oldPlayerState['age']
    newPlayerAge = newPlayerState['age']

    # Different Position case
    if position is not None and newPosition is not None and position != newPosition:
        print('Player changed positions')
        newAvgForOldPosition = 0
        newAvgForNewPosition = 0

        # No players in the old position
        if (currentTotalPlayer - 1) <= 0:
            newAvgForOldPosition = 0
        else:
            newAvgForOldPosition = ((currentAverage * currentTotalPlayer) - oldPlayerAge) / (currentTotalPlayer - 1)
        print('Updated Old position age average: ', newAvgForOldPosition)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position},{"$set": {"avg_age": newAvgForOldPosition}}, upsert=True)

        newAvgForNewPosition = ((npCurrentAverage * npCurrentTotalPlayer) + newPlayerAge) / (npCurrentTotalPlayer + 1)
        print('Updated new position age average: ', newAvgForNewPosition)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": newPosition},{"$set": {"avg_age": newAvgForNewPosition}}, upsert=True)

    # Subtract player from calculation since age/position is cleared or invalid
    elif newPosition is None or newPlayerAge is None or newPlayerAge == 0:
        print('Player age is cleared or new position is empty')
        newPositionAvg = ((currentAverage * currentTotalPlayer) - oldPlayerAge) / (currentTotalPlayer - 1)
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position},{"$set": {"avg_age": newPositionAvg}}, upsert=True)

    # Player from invalid age/position to a valid age/position
    elif (position is None or oldPlayerAge is None or oldPlayerAge == 0) and newPlayerAge > 0:
        print('Player age/position is valid')
        newPositionAvg = ((currentAverage * currentTotalPlayer) + newPlayerAge) / (currentTotalPlayer + 1)
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position},{"$set": {"avg_age": newPositionAvg}}, upsert=True)

    # More checking e.g player switch position, player marked invalid age
    elif oldPlayerAge > 0 and newPlayerAge > 0:
        newPositionAvg = ((currentAverage * currentTotalPlayer) - oldPlayerAge + newPlayerAge) / currentTotalPlayer
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": sportType, "position": position},{"$set": {"avg_age": newPositionAvg}}, upsert=True)

    else:
        print('No updates to position age average')


# Use Flask Framework to create REST endpoint
app = Flask(__name__)
api = Api(app)

# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection[databaseName]

@app.route('/')
def showPlayers():
    return render_template('list.html')

# Test method
@app.route('/test', methods=['GET'])
def test():
    # make an operation to simulate interaction
    #{'ts': Timestamp(1534294127, 1), 't': 4, 'h': 365521937056847418, 'v': 2, 'op': 'i', 'ns': 'sports.soccer',
    # 'ui': UUID('b1ef1848-d533-4f82-a755-efd25365956a'),
    # 'wall': datetime.datetime(2018, 8, 15, 0, 48, 47, 548000), 'o': {'_id': ObjectId('5b73786fa17e67091f89236c'), 'balance': 1000}}
    connection['sports']['soccer'].insert_one({"balance": 1000})

    # {'ts': Timestamp(1534293692, 1), 't': 4, 'h': -5215787170296186624, 'v': 2, 'op': 'u', 'ns': 'sports.soccer',
    # 'ui': UUID('b1ef1848-d533-4f82-a755-efd25365956a'), 'o2': {'_id': ObjectId('5b7371f5a17e6708dd7fc1ee')},
    #  'wall': datetime.datetime(2018, 8, 15, 0, 41, 32, 354000), 'o': {'$v': 1, '$set': {'num': 100}}}
    #connection['sports']['soccer'].update_one({"balance": 1000}, {"$set":{"num": 100}})

    # {'ts': Timestamp(1534294257, 1), 't': 4, 'h': -434037455564944914, 'v': 2, 'op': 'd', 'ns': 'sports.soccer',
    # 'ui': UUID('b1ef1848-d533-4f82-a755-efd25365956a'),
    # 'wall': datetime.datetime(2018, 8, 15, 0, 50, 57, 430000), 'o': {'_id': ObjectId('5b7378d8a17e67093e2afe78')}}
    #connection['sports']['soccer'].delete_one({"balance": 1000})

    #triggers.stop_tail()
    return "hello"

class SportPlayer(Resource):
    # Get a single sport player
    # curl http://127.0.0.1:5000/baseball/player/2165933
    def get(self, sportType, playerId):
        player = getPlayer(db, sportType, playerId)

        if player is None:
            abort(404)  # 404 Resource Not Found

        #return jsonify({"player": player}), 200
        return json.dumps(player)

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
    # return jsonify({'players': playerList}), 200
    # return compressed json
    return json.dumps(playerList)

# Get all types of sports
@app.route('/sports', methods=['GET'])
def getAllSportTypes():
     # Get all collections within a database
     sportList = db.list_collection_names()

     # Remove average collection from list
     sportList.remove(postAvgAgeCollectionName)

     for excludeCol in excludeCollections:
         sportList.remove(excludeCol)
         #pprint(sportList)

     #return jsonify({"sports": sportList}), 200
     return json.dumps(sportList), 200

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
# Flask service will initialise twice, use_reloader=False will prevent that
# app.run(debug =True)
app.run()
