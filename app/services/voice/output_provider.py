from abc import ABC, abstractmethod
class VoiceOutputProvider(ABC):
    @abstractmethod
    def synthesize(self,text:str)->str: ...
