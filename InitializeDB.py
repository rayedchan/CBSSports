import requests
import os
from MongoDB import Connect
from pymongo import MongoClient
from CommonUtils import getAllSports
from Player import Player
from mongotriggers import MongoTrigger
from pprint import pprint

# Name of collection to store position age averages
postAvgAgeCollectionName = 'positionAvgAge'
databaseName = os.environ.get("MONGODB_DBNAME")

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
Setup the average age position collection which stores average age per position
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
    print(sportsJSON)

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
Function to setup triggers on collection
mongotriggers limited in capabilities since every operation in oplog post event
'''
def setup_triggers(connection):
    envWerk = os.environ.get("WERKZEUG_RUN_MAIN")
    print('Value of WERKZEUG', envWerk)

    # The app is not in debug mode or we are in the reloaded process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # Setup triggers
        # Connection must have oplog enable
        # Start mongod with option --replSet rs and then execute rs.initiate() in mongo shell
        triggers = MongoTrigger(connection)

        sportCollections = connection[databaseName].list_collection_names()

        # Put a trigger on each sport collection on insert operation
        for sport in sportCollections:
            # skip position average age collection
            if sport == postAvgAgeCollectionName:
                continue

            print(sport)
            triggers.register_insert_trigger(insert_trigger, databaseName, sport)  # register_op_trigger(func, db_name=None, collection_name=None)
            #triggers.register_update_trigger(notify_manager, databaseName, sport)
            #triggers.register_delete_trigger(notify_manager, databaseName, sport)

        # listens to update/insert/delete by tailing operation log, any of these will trigger the callback
        triggers.tail_oplog()
    else:
        print('setup_triggers function has been called already')

'''
Trigger function to be called on every insertion of a new document into
any sport collection
'''
def insert_trigger(op_document):
    position = op_document['o']['position']
    print(position)

    collectionName = op_document['ns'].split(".")[1]
    print(collectionName)

    # Get total number of documents for specific position with valid age
    currentTotalPlayer = db[collectionName].count_documents({"position": position, "age": {"$gt": 0}})
    print('Total players ', currentTotalPlayer)

    # Get current average for position
    avgCursor = db[postAvgAgeCollectionName].find({"sport_type": collectionName, "position": position})
    currentAverage = 0
    # Iterate results
    for doc in avgCursor:
        pprint(doc)
        currentAverage = doc['avg_age']

    newPlayerAge = op_document['o']['age']
    if newPlayerAge > 0:
        newPositionAvg = ((currentAverage * (currentTotalPlayer - 1)) + newPlayerAge) / currentTotalPlayer
        print('New position age average: ', newPositionAvg)
        db[postAvgAgeCollectionName].update_one({"sport_type": collectionName, "position": position}, {"$set": {"avg_age": newPositionAvg}}, upsert=True)
    else:
        print('No updates to position age average')


# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection[databaseName]

initializeBackend(db)
#setup_triggers(connection)

