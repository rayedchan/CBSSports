import requests
import json

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

for player in players_data:
    firstname = player['firstname']
    lastname = player['lastname']
    pro_status = player['pro_status']
    print(firstname)


