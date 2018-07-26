from pymongo import MongoClient

class Connect(object):
    @staticmethod
    def get_connection():
        return MongoClient("mongodb://admin:Password1@localhost:27017/sports?authSource=admin")