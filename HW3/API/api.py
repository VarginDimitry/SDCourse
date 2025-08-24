from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, FastAPI, File, Form, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl, constr
from starlette.responses import RedirectResponse

app = FastAPI(
    title="MyTube API Gateway",
    version="1.0.0",
    root_path="/api/v1",
    docs_url="/docs",
    swagger_ui_oauth2_redirect_url="/"
)


# ---------- Общие схемы ----------


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class PageMeta(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=200)
    total: int = Field(0, ge=0)


class BaseOK(BaseModel):
    ok: bool = True
    message: str | None = None


class PresignedPart(BaseModel):
    part_number: int = Field(..., ge=1)
    url: HttpUrl


# ---------- Auth ----------

auth = APIRouter(prefix="/auth", tags=["auth"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class LoginRequest(BaseModel):
    email: constr(strip_whitespace=True, min_length=3)
    password: constr(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


@auth.post("/login_oauth", status_code=200)
def login() -> RedirectResponse:
    return RedirectResponse("https://oauth.com/login")


@auth.post("/login", response_model=TokenPair, status_code=200)
def login(body: LoginRequest):
    return TokenPair(access_token="access.demo", refresh_token="refresh.demo")


@auth.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest):
    if not body.refresh_token:
        raise HTTPException(400, "invalid refresh_token")
    return TokenPair(
        access_token="access.refreshed",
        refresh_token=body.refresh_token,
        expires_in=3500,
    )


@auth.post("/logout", response_model=BaseOK, status_code=200)
def logout(authorization: str | None = Header(None)):
    return BaseOK(message="logged out")


# ---------- Users ----------

users = APIRouter(prefix="/users", tags=["users"])


class UserRole(str, Enum):
    user = "user"
    moderator = "moderator"
    admin = "admin"


class UserCreate(BaseModel):
    email: constr(strip_whitespace=True, min_length=3)
    password: constr(min_length=6)
    display_name: constr(min_length=1) | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None
    bio: str | None = None
    role: UserRole = UserRole.user
    created_at: datetime


@users.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate):
    return UserOut(
        id=uuid4(),
        email=body.email,
        display_name=body.display_name,
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


@users.get("/get_me", response_model=UserOut)
def get_me(authorization: str = Header()):
    return UserOut(
        id=user_id,
        email="demo@example.com",
        display_name="Demo",
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


@users.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, body: UserUpdate):
    return UserOut(
        id=user_id,
        email="demo@example.com",
        display_name=body.display_name or "Demo",
        bio=body.bio,
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


# ---------- Videos / Metadata ----------

videos = APIRouter(prefix="/videos", tags=["videos"])


class Visibility(str, Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"


class VideoCreate(BaseModel):
    title: constr(min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] = []
    visibility: Visibility = Visibility.private


class VideoOut(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: str | None = None
    tags: list[str] = []
    visibility: Visibility = Visibility.public
    duration_sec: int | None = None
    status: str = "uploaded"
    created_at: datetime


class VideoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    visibility: Visibility | None = None


@videos.post("", response_model=VideoOut, status_code=201)
def create_video(body: VideoCreate, user_id: UUID):
    return VideoOut(
        id=uuid4(),
        owner_id=user_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        visibility=body.visibility,
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


@videos.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: UUID):
    return VideoOut(
        id=video_id,
        owner_id=uuid4(),
        title="Sample Video",
        visibility=Visibility.public,
        status="ready",
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
        duration_sec=123,
    )


@videos.patch("/{video_id}", response_model=VideoOut)
def update_video(video_id: UUID, body: VideoUpdate):
    return VideoOut(
        id=video_id,
        owner_id=uuid4(),
        title=body.title or "Sample Video",
        description=body.description,
        tags=body.tags or [],
        visibility=body.visibility or Visibility.public,
        status="ready",
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
        duration_sec=123,
    )


@videos.delete("/{video_id}", response_model=BaseOK)
def delete_video(video_id: UUID):
    return BaseOK(message=f"video {video_id} deleted (queued)")


@videos.get("", response_model=list[VideoOut])
def search_videos(
    owner_id: UUID | None = None,
    tag: str | None = None,
    visibility: Visibility | None = None,
    sort: SortOrder = SortOrder.desc,
    page: int = 1,
    size: int = 20,
):
    return [
        VideoOut(
            id=uuid4(),
            owner_id=owner_id or uuid4(),
            title=f"Video {i}",
            visibility=visibility or Visibility.public,
            status="ready",
            created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
        )
        for i in range((page - 1) * size, page * size)
    ]


# ---------- Uploads (S3 presign, multipart) ----------

uploads = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadInitRequest(BaseModel):
    filename: constr(min_length=1)
    content_type: constr(min_length=3)


class UploadInitResponse(BaseModel):
    video_id: UUID


@uploads.post("/upload_video", response_model=UploadInitResponse, status_code=201)
def init_upload(
    filename: Annotated[constr(min_length=1), Form()],
    content_type: Annotated[constr(min_length=3), Form()],
    file: Annotated[bytes, File()],
):
    return UploadInitResponse(video_id=uuid4())


# ---------- Processing / Publish ----------

processing = APIRouter(prefix="/processing", tags=["processing"])


class ProcessStatus(BaseModel):
    video_id: UUID
    status: str  # queued|running|ready|failed
    progress: int = Field(0, ge=0, le=100)


@processing.get("/{video_id}/status", response_model=ProcessStatus)
def get_processing_status(video_id: UUID):
    return ProcessStatus(video_id=video_id, status="running", progress=42)


class PublishRequest(BaseModel):
    video_id: UUID
    make_public: bool = True


class PublishResponse(BaseModel):
    video_id: UUID
    visibility: Visibility
    published_at: datetime


@processing.post("/publish", response_model=PublishResponse)
def publish_video(body: PublishRequest):
    return PublishResponse(
        video_id=body.video_id,
        visibility=Visibility.public if body.make_public else Visibility.unlisted,
        published_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


# ---------- Comments / Likes / Views ----------

social = APIRouter(prefix="/social", tags=["social"])


class CommentCreate(BaseModel):
    video_id: UUID
    text: constr(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: UUID
    video_id: UUID
    author_id: UUID
    text: str
    created_at: datetime


@social.post("/comments", response_model=CommentOut, status_code=201)
def create_comment(body: CommentCreate, x_user_id: UUID | None = Header("u_123")):
    return CommentOut(
        id=uuid4(),
        video_id=body.video_id,
        author_id=x_user_id or "u_123",
        text=body.text,
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


@social.get("/comments/{comment_id}", response_model=CommentOut)
def get_comment(comment_id: UUID):
    return CommentOut(
        id=comment_id,
        video_id=uuid4(),
        author_id=uuid4(),
        text="Nice!",
        created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
    )


@social.delete("/comments/{comment_id}", response_model=BaseOK)
def delete_comment(comment_id: UUID):
    return BaseOK(message=f"comment {comment_id} deleted")


class LikeRequest(BaseModel):
    video_id: UUID
    like: bool = True


class LikeStatus(BaseModel):
    video_id: UUID
    likes: int
    liked_by_me: bool


@social.post("/likes", response_model=LikeStatus)
def set_like(body: LikeRequest, x_user_id: str | None = Header(None)):
    return LikeStatus(
        video_id=body.video_id, likes=101 if body.like else 100, liked_by_me=body.like
    )


class ViewPing(BaseModel):
    video_id: UUID
    position_sec: int = Field(ge=0)


class ViewAck(BaseModel):
    video_id: UUID
    counted: bool
    view_id: UUID | None = None


@social.post("/views", response_model=ViewAck)
def ping_view(body: ViewPing):
    counted = body.position_sec > 10
    return ViewAck(
        video_id=body.video_id, counted=counted, view_id=uuid4() if counted else None
    )


# ---------- Notifications ----------

notif = APIRouter(prefix="/notifications", tags=["notifications"])


class NotifyRequest(BaseModel):
    user_id: UUID
    title: str
    body: str
    deep_link: str | None = None


class NotifyResponse(BaseModel):
    id: UUID
    status: str  # queued|sent|failed


@notif.post("", response_model=NotifyResponse, status_code=202)
def send_notification(body: NotifyRequest):
    return NotifyResponse(id=uuid4(), status="queued")


# ---------- Statistics / Analytics ----------

stats = APIRouter(prefix="/stats", tags=["stats"])


class VideoStats(BaseModel):
    video_id: UUID
    views: int
    likes: int
    comments: int
    watch_time_sec: int


class UserStats(BaseModel):
    user_id: UUID
    videos: int
    views: int
    likes: int
    comments: int


@stats.get("/video/{video_id}", response_model=VideoStats)
def get_video_stats(video_id: UUID):
    return VideoStats(
        video_id=video_id, views=1234, likes=120, comments=15, watch_time_sec=98765
    )


@stats.get("/user/{user_id}", response_model=UserStats)
def get_user_stats(user_id: UUID):
    return UserStats(user_id=user_id, videos=7, views=43210, likes=987, comments=321)


# ---------- Search / Discovery ----------

search = APIRouter(prefix="/search", tags=["search"])


class SearchResponse(BaseModel):
    meta: PageMeta
    items: list[VideoOut]


@search.get("/videos", response_model=SearchResponse)
def search_videos_global(
    q: str | None = None,
    tag: str | None = None,
    sort: SortOrder = SortOrder.desc,
    page: int = 1,
    size: int = 20,
):
    items = [
        VideoOut(
            id=uuid4(),
            owner_id=uuid4(),
            title=f"Found {q or tag or i}",
            visibility=Visibility.public,
            status="ready",
            created_at=datetime.now(tz=ZoneInfo("Europe/Moscow")),
        )
        for i in range((page - 1) * size, page * size)
    ]
    return SearchResponse(meta=PageMeta(page=page, size=size, total=1000), items=items)


# ---------- Service / Health ----------

service = APIRouter(prefix="/service", tags=["service"])


class Health(BaseModel):
    status: str = "ok"
    time: datetime


@service.get("/healthcheck", response_model=Health)
def healthcheck():
    return Health(time=datetime.now(tz=ZoneInfo("Europe/Moscow")))


# ---------- Маршрутизация ----------

app.include_router(auth)
app.include_router(users)
app.include_router(videos)
app.include_router(uploads)
app.include_router(processing)
app.include_router(social)
app.include_router(notif)
app.include_router(stats)
app.include_router(search)
app.include_router(service)
