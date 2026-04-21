from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["ui"])


@router.get("/ui/chat", include_in_schema=False)
async def chat_ui() -> FileResponse:
    html_path = Path(__file__).resolve().parent.parent / "static" / "chat.html"
    return FileResponse(html_path)
