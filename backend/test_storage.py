from app.services.storage import upload_briefing_audio


audio_path = "tmp/test-morning-brief.mp3"

storage_path = upload_briefing_audio(
    file_path=audio_path,
    storage_path="test/test-morning-brief.mp3",
)

print()
print("==============================")
print("STORAGE UPLOAD SUCCESS")
print("==============================")
print("Storage path:", storage_path)