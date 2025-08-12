from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl


class DownloadRequest(BaseModel):
    url: HttpUrl
    format: Literal["audio", "video"] = "video"


class ConvertResponse(BaseModel):
    filename: str
    message: str
    file_path: str
    file_type: Literal["mp3", "mp4"]


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class JobStatus(BaseModel):
    id: str
    state: Literal["queued", "running", "done", "error"]
    progress: float = 0.0
    message: Optional[str] = None
