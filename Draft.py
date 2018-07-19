import requests
import json
from MongoDB import Connect
from pymongo import MongoClient
from pprint import pprint

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

'''
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

    print(id)
    print(firstname)
    print(lastname)
    print(position)
    print(age)
    print()
'''

# MongoDB connection
connection = Connect.get_connection()

# Access database
db = connection.test

# Query collection with filter
cursor = db.inventory.find({"status": "D"})

# iterate results
for inventory in cursor:
     pprint(inventory)