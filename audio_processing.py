import requests
import os
from dotenv import load_dotenv

load_dotenv()

class VoiceGenerator_ElevenLabs:

    CHUNK_SIZE = 1024

    def __init__(self):
        self.speaker_urls = {
            "Dave": "https://api.elevenlabs.io/v1/text-to-speech/CYw3kZ02Hs0563khs1Fj",
            "Charlie": "https://api.elevenlabs.io/v1/text-to-speech/IKne3meq5aSn9XLyUdCD",
            "Jack": "https://api.elevenlabs.io/v1/text-to-speech/iwZJs1aNhjvXWUPoqjEW"
        }

    def gen_audio(self, text, output_audio_path, speaker="Dave", chunk_size=1024):
        xi_api_key = os.getenv('XI_API_KEY')
        url = self.speaker_urls.get(speaker)
        if not url:
            raise ValueError("Invalid speaker")

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": xi_api_key
        }

        data = {
            "model_id": "eleven_multilingual_v2",
            "text": text,
            "voice_settings": {"similarity_boost": 0.5, "stability": 0.5}
        }

        response = requests.post(url, json=data, headers=headers)
        with open(output_audio_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)