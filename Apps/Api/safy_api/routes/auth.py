from fastapi import APIRouter
router=APIRouter()
OWNER='auth'
def describe(): return {'domain':'auth','router': True}
