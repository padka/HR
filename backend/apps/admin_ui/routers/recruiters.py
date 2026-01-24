from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


@router.get("", response_class=HTMLResponse)
async def recruiters_list(request: Request):
    return RedirectResponse(url="/app/recruiters", status_code=302)


@router.get("/new", response_class=HTMLResponse)
async def recruiters_new(request: Request):
    return RedirectResponse(url="/app/recruiters/new", status_code=302)


@router.post("/create")
async def recruiters_create(request: Request):
    return RedirectResponse(url="/app/recruiters", status_code=303)


@router.get("/{rec_id}/edit", response_class=HTMLResponse)
async def recruiters_edit(request: Request, rec_id: int):
    return RedirectResponse(url=f"/app/recruiters/{rec_id}/edit", status_code=302)


@router.post("/{rec_id}/update")
async def recruiters_update(request: Request, rec_id: int):
    return RedirectResponse(url=f"/app/recruiters/{rec_id}/edit", status_code=303)


@router.post("/{rec_id}/delete")
async def recruiters_delete(rec_id: int):
    return RedirectResponse(url="/app/recruiters", status_code=303)
