from app.services.tts.azure import generate_speech


text = """
မင်္ဂလာနံနက်ခင်းပါရှင်။

ဒီနေ့အတွက် အရေးကြီးတဲ့ သတင်းအချက်အလက်တွေကို
Morning Brief ကနေ တင်ဆက်ပေးသွားမှာ ဖြစ်ပါတယ်။

နည်းပညာ၊ စီးပွားရေး၊ ကမ္ဘာ့သတင်းနဲ့
ဘောလုံးသတင်းတွေကို အတိုချုံးနားဆင်နိုင်ပါတယ်။
"""


output = generate_speech(
    text=text,
    output_path="tmp/test-morning-brief.mp3",
)


print()
print("================================")
print("AZURE TTS SUCCESS")
print("================================")
print("Audio:", output)
print("================================")