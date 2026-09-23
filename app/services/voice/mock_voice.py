from .input_provider import VoiceInputProvider
from .output_provider import VoiceOutputProvider
class MockVoiceInput(VoiceInputProvider):
    def transcribe(self,audio_reference): return f'[voice transcript placeholder: {audio_reference}]'
class MockVoiceOutput(VoiceOutputProvider):
    def synthesize(self,text): return f'[voice output placeholder: {text}]'
