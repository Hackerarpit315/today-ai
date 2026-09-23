from abc import ABC, abstractmethod
class VoiceInputProvider(ABC):
    @abstractmethod
    def transcribe(self,audio_reference:str)->str: ...
