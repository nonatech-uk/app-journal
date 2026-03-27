from fastapi import APIRouter, Depends

from src.api.deps import CurrentUser, get_current_user
from src.api.models import UserOut

router = APIRouter()


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(email=user.email, display_name=user.display_name, role=user.role)
