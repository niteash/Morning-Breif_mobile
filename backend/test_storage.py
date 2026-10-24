from app.services.storage import (
    upload_briefing_audio,
    create_briefing_signed_url,
)


TEST_AUDIO = "tmp/test-morning-brief.mp3"

STORAGE_PATH = "test/test-morning-brief.mp3"


print("Uploading audio...")

uploaded_path = upload_briefing_audio(
    TEST_AUDIO,
    STORAGE_PATH,
)

print()
print("Uploaded:")
print(uploaded_path)


print()
print("Creating signed URL...")

signed_url = create_briefing_signed_url(
    STORAGE_PATH,
    expires_in=3600,
)

print()
print("Signed URL:")
print(signed_url)