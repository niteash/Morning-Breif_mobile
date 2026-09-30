# Morning Brief 📰🎧

> A Burmese-language AI morning briefing app that turns the most relevant daily news into a personalized audio briefing.

Morning Brief is an Android-first mobile application designed for users who want to stay informed without spending a lot of time reading individual news articles.

Users select the topics they care about, choose their preferred delivery time, and receive a personalized morning briefing containing the most relevant stories across their selected categories.

The briefing is generated in Burmese using AI and converted into natural Burmese speech using Azure Neural TTS.

---

## ✨ Features

### 📰 Personalized News

Users can select the categories they want to follow, such as:

- 🌍 World
- ⚽ Football
- 💼 Business
- 💻 Technology
- 🇲🇲 Myanmar

The backend retrieves and filters recent stories based on the user's selected categories.

### 🤖 AI-Powered Briefing

Instead of simply displaying a list of articles, Morning Brief uses Gemini to transform selected news stories into a concise spoken briefing.

The AI:

- Selects important stories
- Removes unnecessary repetition
- Combines related stories
- Summarizes information naturally
- Generates Burmese-language narration
- Avoids fabricating information
- Keeps technical names and terms in English when appropriate

### 🎙️ Burmese Neural TTS

The generated Burmese briefing is converted into speech using:

**Azure Speech Services**

Current voice:

```text
my-MM-NilarNeural
