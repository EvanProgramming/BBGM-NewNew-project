from fastapi import APIRouter, Depends

from deps import get_current_user
from games.ai import GomokuPlayRequest, PlayRequest, gomoku_play, play
from models import User

router = APIRouter()


@router.post("/games/gomoku/play")
def gomoku(payload: GomokuPlayRequest, _: User = Depends(get_current_user)):
    return gomoku_play(payload)


@router.post("/games/chess/play")
def chess(payload: PlayRequest, _: User = Depends(get_current_user)):
    return play(payload)
