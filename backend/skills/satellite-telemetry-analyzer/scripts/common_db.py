# scripts/common_db.py
DB_CONFIG = {
    "host": "10.201.0.223",
    "port": 9030,
    "user": "mxbc",
    "password": "mxbc1234",
    "database": "mxbc_demo",
    "charset": "utf8mb4",
    "connect_timeout": 5
}
def normalize_satellites(satellites):
    if not satellites:
        return satellites
    if isinstance(satellites, list):
        return [s.replace(" ", "") for s in satellites]
    return satellites