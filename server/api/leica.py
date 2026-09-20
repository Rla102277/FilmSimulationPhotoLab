from fastapi import APIRouter, HTTPException
from core.leica.authoritative import load_authoritative_manifest, verify_authoritative_archive

router = APIRouter(prefix="/leica", tags=["leica"])

@router.get("/v1.2/verify")
def verify():
    return verify_authoritative_archive()

@router.get("/v1.2/looks")
def looks():
    try:
        return load_authoritative_manifest()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
