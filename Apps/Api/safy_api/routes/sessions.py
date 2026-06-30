from fastapi import APIRouter
router=APIRouter()
OWNER='sessions'
def describe(): return {'domain':'sessions','router': True}
