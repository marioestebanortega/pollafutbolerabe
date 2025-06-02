from pymongo import MongoClient

uri = "mongodb+srv://polllaadmin:polllaadmin@clusterpolla.oenhvvv.mongodb.net/?retryWrites=true&w=majority&appName=ClusterPolla"
client = MongoClient(uri)

try:
    dbs = client.list_database_names()
    print("[OK] Conexión exitosa. Bases de datos:", dbs)
except Exception as e:
    print("[ERROR] No se pudo conectar:", e)