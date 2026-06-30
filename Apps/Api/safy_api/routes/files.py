from fastapi import APIRouter
router=APIRouter()
OWNER='files'
def describe(): return {'domain':'files','router': True}
