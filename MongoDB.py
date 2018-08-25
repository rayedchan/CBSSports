from pymongo import MongoClient
import os

class Connect(object):
    @staticmethod
    def get_connection():
        return MongoClient(os.environ.get("MONGODB_URI"))