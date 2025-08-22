#!/usr/bin/python
#!/usr/bin/env python3
"""
Auto-upload to YouTube and publish immediately as public.

Required scopes:
  • https://www.googleapis.com/auth/youtube.upload
"""
import http.client as httplib
import httplib2
import json
import os, random, shutil, subprocess, sys, time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import argparse
from types import SimpleNamespace

# ─── Retry / upload constants ──────────────────────────────────────────────────
httplib2.RETRIES = 1
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error, IOError, httplib.NotConnected,
    httplib.IncompleteRead, httplib.ImproperConnectionState,
    httplib.CannotSendRequest, httplib.CannotSendHeader,
    httplib.ResponseNotReady, httplib.BadStatusLine,
)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# ─── OAuth / API constants ─────────────────────────────────────────────────────
UPLOAD_SCOPE   = "https://www.googleapis.com/auth/youtube.upload"
SCOPES = [UPLOAD_SCOPE]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION      = "v3"
VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

# ───────────────────────────────────────────────────────────────────────────────
def get_authenticated_service(assetspath):
    """
    Re-auth if needed; cache user OAuth tokens in a separate token file
    """
    if not assetspath:
        raise ValueError("assetspath is required for authentication")
    
    creds = None
    
    # Use authentication files from assetspath
    token_file = os.path.join(assetspath, "youtube_token.json")
    client_secrets_file = os.path.join(assetspath, "client_secret.json")
    
    scopes = SCOPES        # instead of [UPLOAD_SCOPE, READONLY_SCOPE]

    # Load existing credentials from token file
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    # If there are no valid credentials available, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        # If refresh failed or no valid creds, run the OAuth flow
        if not creds:
            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(f"Client secrets file not found: {client_secrets_file}")
            
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, "w") as token:
            token.write(creds.to_json())

    service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)
    return service


def initialize_upload(youtube, options):
    """
    Uploads the file as **public**, returns the new video_id.
    """
    tags = options.keywords.split(",") if options.keywords else None

    body = dict(
        snippet=dict(
            title       = options.title,
            description = options.description,
            tags        = tags,
            categoryId  = options.category,
        ),
        status=dict(
            privacyStatus="public",            ### CHANGED: always public immediately
            selfDeclaredMadeForKids=False,
        ),
    )

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True),
    )
    return resumable_upload(insert_request)      ### CHANGED: now returns video_id


def resumable_upload(insert_request):
    """
    Standard exponential-backoff upload. Returns the video_id when done.
    """
    response, error, retry = None, None, 0
    
    while response is None:
        try:
            status, response = insert_request.next_chunk()
            
            if response is not None and "id" in response:
                vid = response["id"]
                return vid
            else:
                sys.exit(f"Unexpected upload response: {response}")
                
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status}: {e.content}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error:
            retry += 1
            if retry > MAX_RETRIES:
                sys.exit("Giving up.")
            sleep = random.random() * (2 ** retry)
            time.sleep(sleep)
            error = None  # Reset error for next iteration


# ─── Thumbnail setting logic ──────────────────────────────────────────────────
def set_thumbnail(youtube, video_id, thumbnail_path):
    """
    Set the thumbnail for a YouTube video.
    
    Args:
        youtube: Authenticated YouTube service
        video_id: YouTube video ID
        thumbnail_path: Path to the thumbnail image file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"🖼️  Setting thumbnail for video {video_id}")
        
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path)
        ).execute()
        
        print(f"✅ Thumbnail set successfully")
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "doesn't have permissions to upload and set custom video thumbnails" in error_msg:
            print(f"⚠️  Thumbnail upload skipped: Your YouTube channel needs to be verified to upload custom thumbnails")
            print(f"   You can verify your channel at: https://www.youtube.com/verify")
            print(f"   Once verified, you can manually set the thumbnail from: {thumbnail_path}")
        else:
            print(f"❌ Failed to set thumbnail: {e}")
        return False



def publish_simple(title: str, file_path: str, description: str, assetspath: str,
                   thumbnail_path: str = None, category: str = "22", keywords: str = "") -> str:
    """
    Convenience one-shot publish:
      1) auth
      2) upload as *public*
      3) (optional) set custom thumbnail
    Returns the watch URL.
    """
    yt = get_authenticated_service(assetspath)
    opts = SimpleNamespace(
        title=title,
        description=description,
        category=category,
        keywords=keywords,
        file=file_path,
    )
    video_id = initialize_upload(yt, opts)
    
    # Try to set thumbnail if provided, but don't fail the upload if it doesn't work
    if thumbnail_path:
        thumbnail_success = set_thumbnail(yt, video_id, thumbnail_path)
        if not thumbnail_success:
            print("⚠️  Continuing with upload despite thumbnail failure...")
    
    print(f"Video {video_id} published as public: https://www.youtube.com/watch?v={video_id}")
    return f"https://www.youtube.com/watch?v={video_id}"

def _probe_short_file(file_path: str) -> None:
    """
    Best-effort sanity checks for Shorts:
      • Warn if duration > 180s (3 min)
      • Warn if not vertical (height <= width)
    Uses ffprobe if available; otherwise no-ops.
    """
    try:
        if not shutil.which("ffprobe"):
            print("ℹ️  ffprobe not found; skipping Shorts validation.")
            return
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-print_format", "json", file_path],
            capture_output=True, text=True, check=True
        )
        info = json.loads(proc.stdout)
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        width, height = int(v.get("width", 0)), int(v.get("height", 0))
        # duration may be on stream or format; take whichever is present
        dur_s = float(v.get("duration") or info.get("format", {}).get("duration") or 0.0)

        if dur_s > 180.5:
            print(f"⚠️  Duration ~{dur_s:.1f}s > 180s. Shorts are up to 3 minutes.")
        if height <= width:
            print(f"⚠️  Video is not vertical ({width}x{height}). Shorts work best vertical.")

    except Exception as e:
        print(f"ℹ️  Shorts validation skipped: {e}")


def publish_short(
    title: str,
    file_path: str,
    assetspath: str,
    base_description: str = "",
    full_video_url: str = "",
    *,
    timestamp_seconds: int | None = None,   # if set, appends &t=...s to full_video_url
    include_hashtag_shorts: bool = False,
    thumbnail_path: str | None = None,
    category: str = "22",
    keywords: str = ""
) -> str:
    """
    Upload a YouTube Short (<=3 min, vertical) as public immediately.
    Returns the watch URL.

    Linking to full video:
      • Puts a clickable YouTube link at the very top of the Short's description.
      • For the in-app Shorts "Related video" pill, set it later in YouTube Studio.
        (Not exposed via the Data API.)
    """
    # Build description with the full video URL at the top.
    desc_lines = []
    if full_video_url:
        link = full_video_url.strip()
        if timestamp_seconds is not None and timestamp_seconds >= 0:
            # Add &t=...s to either /watch?v=... or youtu.be/... forms.
            if "watch?v=" in link:
                sep = "&" if "?" in link else "?"
                link = f"{link}{sep}t={int(timestamp_seconds)}s"
            elif "youtu.be/" in link:
                sep = "?" if "?" not in link else "&"
                link = f"{link}{sep}t={int(timestamp_seconds)}s"
        desc_lines.append(f"Full video: {link}")
    if base_description:
        desc_lines.append(base_description)
    if include_hashtag_shorts:
        desc_lines.append("#Shorts")
    final_description = "\n\n".join([s for s in desc_lines if s]).strip()

    # Optional sanity checks for Shorts constraints
    _probe_short_file(file_path)

    yt = get_authenticated_service(assetspath)
    opts = SimpleNamespace(
        title=title,
        description=final_description,
        category=category,
        keywords=keywords,
        file=file_path,
    )

    vid = initialize_upload(yt, opts)

    if thumbnail_path:
        try:
            set_thumbnail(yt, vid, thumbnail_path)
        except Exception as e:
            print(f"⚠️  Thumbnail step failed/skipped: {e}")

    url = f"https://www.youtube.com/watch?v={vid}"
    print(f"✅ Short published: {url}")
    return url


# ─── CLI boilerplate ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    pass
    # publish_simple(
    #     title="Test Title",
    #     file_path="output_overlay.mp4",
    #     description="Test Description",
    #     thumbnail_path="cache/thumbnails/28f4eb7f861db4adcdbe2d9d72608f38.png",
    #     category="27",
    #     keywords=""
    # )

    # publish_short(
    #     title="No-Fly List",
    #     file_path="cache/shorts/short_9x16_captions_speed2x_421d97c034d6e00acac7e9be9c6ca3a7.mp4",
    #     base_description="Check out the full video on our channel now!",
    # )


    # parser = argparse.ArgumentParser()
    # parser.add_argument("--file", help="Video file to upload (optional for auth-only)")
    # parser.add_argument("--title", default="Test Title", help="Video title")
    # parser.add_argument("--description", default="Test Description")
    # parser.add_argument("--category", default="22", help="Numeric video category")
    # parser.add_argument("--keywords", default="", help="Comma-separated keywords")
    # args = parser.parse_args()

    # # Just do auth flow if no file specified
    # if not args.file:
    #     print("No file specified - running auth flow only...")
    #     get_authenticated_service()
    #     print("Authentication complete! .json file should now be available.")
    #     sys.exit(0)

    # if not os.path.exists(args.file):
    #     sys.exit("Invalid --file path")
    
    # yt = get_authenticated_service()

    # try:
    #     vid = initialize_upload(yt, args)
    #     poll_and_publish(yt, vid)
        
    # except HttpError as e:
    #     print(f"HTTP error occurred: {e.resp.status} - {e.content}")