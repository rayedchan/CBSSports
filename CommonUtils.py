import requests

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