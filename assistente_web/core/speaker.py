# Módulo Speaker Adaptado para Django: Responsável pela síntese de voz (TTS)

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Só importa pyttsx3 quando a funcionalidade estiver habilitada
_TTS_ENABLED = getattr(settings, "ASSISTANT_TTS_ENABLED", False)
if _TTS_ENABLED:
    try:
        import pyttsx3

        PYTTSX3_AVAILABLE = True
    except ImportError as e:
        logger.info(f"pyttsx3 não disponível: {e}")
        pyttsx3 = None
        PYTTSX3_AVAILABLE = False
else:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False


class DjangoSpeaker:
    def __init__(self):
        """Inicializa o motor TTS (pyttsx3)."""
        self.engine = None

        if not PYTTSX3_AVAILABLE:
            logger.debug("TTS desabilitado (ASSISTANT_TTS_ENABLED=False) ou pyttsx3 indisponível.")
            return

        try:
            self.engine = pyttsx3.init()
            # Configurações padrão ou do Django settings
            rate = getattr(settings, "ASSISTANT_SPEECH_RATE", 150)
            self.engine.setProperty("rate", rate)

            # Opcional: Configurar voz específica
            voices = self.engine.getProperty("voices")
            if voices:
                voice_id = getattr(settings, "ASSISTANT_VOICE_ID", None)
                if voice_id:
                    self.engine.setProperty("voice", voice_id)
                else:
                    # Usar primeira voz disponível
                    self.engine.setProperty("voice", voices[0].id)

            logger.info("Motor TTS (pyttsx3) inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro crítico ao inicializar o motor pyttsx3: {e}")
            logger.warning("Funcionalidade de fala estará desabilitada.")
            self.engine = None

    def is_available(self):
        """Verifica se o motor TTS está disponível."""
        return self.engine is not None and PYTTSX3_AVAILABLE

    def speak(self, text, display_only=False):
        """Converte o texto fornecido em fala.

        Args:
            text (str): O texto a ser falado.
            display_only (bool): Se True, apenas exibe o texto sem falar.
        """
        if display_only or not self.engine:
            # Apenas registra o texto sem falar
            logger.info(f"Assistente: {text}")
            return text

        try:
            logger.info(f"Assistente (falando): {text}")
            self.engine.say(text)
            self.engine.runAndWait()
            return text
        except Exception as e:
            logger.error(f"Erro durante a síntese de voz: {e}")
            # Fallback: Apenas registra se a fala falhar
            logger.info(f"Assistente (fallback): {text}")
            return text

    def get_available_voices(self):
        """Retorna lista de vozes disponíveis."""
        if not self.engine or not PYTTSX3_AVAILABLE:
            return []

        try:
            voices = self.engine.getProperty("voices")
            return [{"id": v.id, "name": v.name, "languages": getattr(v, "languages", [])} for v in voices]
        except Exception as e:
            logger.error(f"Erro ao obter vozes disponíveis: {e}")
            return []

    def set_voice(self, voice_id):
        """Define a voz a ser usada."""
        if not self.engine or not PYTTSX3_AVAILABLE:
            return False

        try:
            self.engine.setProperty("voice", voice_id)
            return True
        except Exception as e:
            logger.error(f"Erro ao definir voz {voice_id}: {e}")
            return False

    def set_rate(self, rate):
        """Define a velocidade da fala."""
        if not self.engine or not PYTTSX3_AVAILABLE:
            return False

        try:
            self.engine.setProperty("rate", rate)
            return True
        except Exception as e:
            logger.error(f"Erro ao definir velocidade {rate}: {e}")
            return False
