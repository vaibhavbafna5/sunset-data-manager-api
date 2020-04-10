from pymongo import MongoClient

client = MongoClient("mongodb+srv://sunset-data-manager-admin:sunset442@cluster0-stvht.mongodb.net/test?retryWrites=true&w=majority")
db = client['ImageMetaData']

image_collection = db['Images']
logs_collection = db['Logs']

print(image_collection.estimated_document_count())
image_collection.remove({})
logs_collection.remove({})

print("Tactical nuke has been deployed.")