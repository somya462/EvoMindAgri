from pymongo import MongoClient
from config import Config

client = MongoClient(
    Config.MONGO_URI,
    serverSelectionTimeoutMS=3000
)

db = client[Config.MONGO_DB_NAME]

users_collection = db["users"]
conversations_collection = db["conversations"]
messages_collection = db["messages"]

# ADAPTIVE MEMORY ENGINE COLLECTIONS

# Stores approved agricultural memories
memories_collection = db["memories"]

# Stores memory proposals awaiting approval
memory_proposals_collection = db["memory_proposals"]

# Stores previous versions of updated memories
memory_versions_collection = db["memory_versions"]

# Stores memory-related activity and audit records
memory_audit_collection = db["memory_audit"]
