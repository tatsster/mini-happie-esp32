"""Route: GET /manifest.json"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server import storage

router = APIRouter()


@router.get("/manifest.json")
def get_manifest() -> JSONResponse:
    # Import lazily so monkeypatching server.main.MANIFEST_PATH in tests is
    # visible at call time without creating a circular import at module load.
    import server.main as _main

    return JSONResponse(content=storage._read_manifest(_main.MANIFEST_PATH))
