from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_class=HTMLResponse)
async def questions_list(request: Request):
    return RedirectResponse(url="/app/questions", status_code=302)


@router.get("/{question_id}/edit", response_class=HTMLResponse)
async def questions_edit(request: Request, question_id: int):
    return RedirectResponse(url=f"/app/questions/{question_id}/edit", status_code=302)


@router.post("/{question_id}/update")
async def questions_update(request: Request, question_id: int):
    return RedirectResponse(url=f"/app/questions/{question_id}/edit", status_code=303)


__all__ = ["router"]
