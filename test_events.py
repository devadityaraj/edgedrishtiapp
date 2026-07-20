import asyncio
from backend.db.session import DatabaseManager
from backend.api.user_routes import list_events
from backend.db.models import MasterAdmin

async def run():
    db = DatabaseManager.get_session()
    try:
        master = db.query(MasterAdmin).first()
        res = await list_events(limit=5, offset=0, current_user=master, db=db, camera_id=None, event_type=None)
        print("Success:", res)
    finally:
        db.close()

asyncio.run(run())
