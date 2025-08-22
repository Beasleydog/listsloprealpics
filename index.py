from runit import runit
from upload_video import get_authenticated_service

runit("profiles/naturelist")
runit("profiles/govlist")