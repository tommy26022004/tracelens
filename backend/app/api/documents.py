from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/upload")
async def upload(file: UploadFile) -> dict[str, str]:
    return {"filename": file.filename or "", "status": "not-implemented"}
