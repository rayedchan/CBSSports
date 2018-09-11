# CBSSports
Description: Use CBS Sports REST API to fetch sport players. 
MongoDB is used to store data.
Python and Flask are used to create custom REST interface.
AngularJS is used to built UI and makes calls to the custom REST endpoints. 

API Reference: http://developer.cbssports.com/documentation/api/files/sports

URL: https://cbssports.herokuapp.com/


# Database Design
Type = MongoDB

Collections
<sport_type> - stores all the players from the specific sport
sport - stores all the type of sports
positionAvgAge - stores all the position age averages from each sport

