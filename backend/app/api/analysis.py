from fastapi import APIRouter

router = APIRouter()


@router.post("/run")
async def run_analysis(application_id: str) -> dict[str, str]:
    return {"application_id": application_id, "status": "not-implemented"}
