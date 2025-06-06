import uuid
import os
import zipfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Backend is working!"}

@app.post("/upload-prd")
async def upload_prd(
    file: UploadFile = File(...),
    title: str = Form(...),
    user_id: str = Form(...)
):
    max_size_bytes = 50 * 1024 * 1024  # 50 MB
    content = await file.read()

    if len(content) > max_size_bytes:
        raise HTTPException(status_code=400, detail="File too large. Limit is 50MB.")

    allowed_types = {
        "application/pdf": "pdf",
        "text/plain": "txt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/zip": "zip"
    }

    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_ext = allowed_types[file.content_type]

    if file_ext == "zip":
        try:
            with zipfile.ZipFile(file.file) as zf:
                valid_files = [
                    name for name in zf.namelist()
                    if name.endswith((".pdf", ".docx", ".txt")) and not name.startswith("__MACOSX/")
                ]
                if len(valid_files) != 1:
                    raise HTTPException(status_code=400, detail="Zip must contain exactly one valid PRD file.")

                with zf.open(valid_files[0]) as unzipped_file:
                    prd_bytes = unzipped_file.read()
                    file_ext = valid_files[0].split(".")[-1]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract zip: {str(e)}")
    else:
        prd_bytes = content

    storage_path = f"{user_id}/{str(uuid.uuid4())}.{file_ext}"
    try:
        supabase.storage.from_("prd-files").upload(
            path=storage_path,
            file=prd_bytes,
            file_options={"content-type": "application/octet-stream"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    file_url = f"{SUPABASE_URL}/storage/v1/object/public/prd-files/{storage_path}"

    try:
        supabase.table("prds").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "file_url": file_url
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {str(e)}")

    return {"status": "success", "file_url": file_url}
