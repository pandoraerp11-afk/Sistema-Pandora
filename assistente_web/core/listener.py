# Módulo Listener Adaptado para Django: Responsável por ouvir ou ler a entrada do usuário

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Importa speech_recognition apenas se a funcionalidade estiver habilitada via settings
_VOICE_ENABLED = getattr(settings, "ASSISTANT_SPEECH_ENABLED", False)
if _VOICE_ENABLED:
    try:
        import speech_recognition as sr

        SPEECH_RECOGNITION_AVAILABLE = True
    except ImportError as e:
        # Log discreto, não poluir startup
        logger.info(f"Speech recognition não disponível: {e}")
        sr = None
        SPEECH_RECOGNITION_AVAILABLE = False
else:
    sr = None
    SPEECH_RECOGNITION_AVAILABLE = False


class DjangoListener:
    def __init__(self):
        """Inicializa o reconhecedor de voz e verifica o microfone."""
        self.recognizer = None
        self.microphone = None

        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.debug("Speech recognition desabilitado (ASSISTANT_SPEECH_ENABLED=False) ou não disponível.")
            return

        try:
            self.recognizer = sr.Recognizer()
            # Tenta encontrar um microfone
            self.microphone = sr.Microphone()
            # Ajusta para ruído ambiente uma vez na inicialização
            with self.microphone as source:
                logger.info("Ajustando para ruído ambiente...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Microfone encontrado e inicializado.")
        except Exception as e:
            logger.error(f"Erro ao inicializar o microfone: {e}")
            self.microphone = None
            self.recognizer = None

    def has_microphone(self):
        """Verifica se há microfone disponível."""
        return self.microphone is not None and SPEECH_RECOGNITION_AVAILABLE

    def listen_voice_from_audio(self, audio_data):
        """Processa áudio enviado via web (base64 ou arquivo).

        Args:
            audio_data: Dados de áudio para processar

        Returns:
            str: O texto reconhecido do comando de voz, ou None se não conseguiu ouvir.
        """
        if not SPEECH_RECOGNITION_AVAILABLE or not self.recognizer:
            logger.warning("Speech recognition não disponível")
            return None

        try:
            # Aqui você pode implementar a lógica para processar áudio da web
            # Por exemplo, convertendo de base64 para dados de áudio
            command = self.recognizer.recognize_google(audio_data, language="pt-BR")
            logger.info(f"Reconhecido: {command}")
            return command.lower()
        except Exception as e:
            logger.error(f"Erro durante o reconhecimento de voz: {e}")
            return None

    def process_text_input(self, text_input):
        """Processa entrada de texto do usuário via web.

        Args:
            text_input (str): Texto digitado pelo usuário

        Returns:
            str: Texto processado e limpo
        """
        if not text_input:
            return None

        processed = text_input.lower().strip()
        logger.info(f"Texto processado: {processed}")
        return processed

    def listen_voice(self):
        """Ouve o comando de voz do usuário usando o microfone (para uso local).

        Returns:
            str: O texto reconhecido do comando de voz, ou None se não conseguiu ouvir.
        """
        if not SPEECH_RECOGNITION_AVAILABLE or not self.microphone or not self.recognizer:
            logger.warning("Tentativa de ouvir voz sem recursos disponíveis.")
            return None

        with self.microphone as source:
            logger.info("Ouvindo...")
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except Exception as e:
                logger.warning(f"Erro ao capturar áudio: {e}")
                return None

        try:
            logger.info("Reconhecendo...")
            command = self.recognizer.recognize_google(audio, language="pt-BR")
            logger.info(f"Reconhecido: {command}")
            return command.lower()
        except Exception as e:
            logger.error(f"Erro durante o reconhecimento de voz: {e}")
            return None
