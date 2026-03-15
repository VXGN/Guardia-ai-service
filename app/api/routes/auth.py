from fastapi import APIRouter, Depends
from app.core.firebase import verify_firebase_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/verify")
async def verify_token(payload: dict = Depends(verify_firebase_token)):
    return {
        "success": True,
        "uid": payload.get("uid") or payload.get("user_id"),
        "email": payload.get("email"),
    }
