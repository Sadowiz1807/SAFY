from fastapi import APIRouter
from Apps.Api.safy_api.runtime_store import envelope
router=APIRouter()
@router.get('/runtime/health')
def runtime_health(): return envelope({'status':'ok','served_by':'routes/health.py'})
