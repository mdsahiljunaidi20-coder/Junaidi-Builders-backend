import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://sahiljunaidi25_db_user:gOcAVS5J5Ie2rzDm@junaidibuilders.9ltpo0t.mongodb.net/?appName=JunaidiBuilders")
DB_NAME = os.getenv("DB_NAME", "junaidi_builders")

client = None
db = None


async def connect_db():
    global client, db

    # Try real MongoDB first, fall back to in-memory mock
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        test_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
        await test_client.server_info()  # Will raise if MongoDB is not reachable
        client = test_client
        db = client[DB_NAME]
        print(f"✅ Connected to MongoDB: {DB_NAME}")
    except Exception as e:
        from mongomock_motor import AsyncMongoMockClient
        client = AsyncMongoMockClient()
        db = client[DB_NAME]
        print(f"⚠️  MongoDB connection failed: {e}")
        print(f"⚠️  Using in-memory mock database (Data will NOT persist!)")

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.labours.create_index("site_id")
    await db.attendance.create_index([("site_id", 1), ("date", 1)])
    await db.attendance.create_index([("labour_id", 1), ("date", 1)])
    await db.expenses.create_index("site_id")
    await db.advances.create_index("labour_id")
    await db.allocations.create_index([("date", 1), ("site_id", 1)])
    await db.allocations.create_index([("date", 1), ("labour_id", 1)])


async def close_db():
    global client
    if client:
        client.close()
        print("❌ Database connection closed")


def get_db():
    return db
