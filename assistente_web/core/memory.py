# Módulo Memory Adaptado para Django: Responsável pelo armazenamento e recuperação de informações

import logging

from django.db import models
from django.utils import timezone

from ..models import MemoriaAssistente

logger = logging.getLogger(__name__)


class DjangoMemory:
    def __init__(self, user):
        """Inicializa o sistema de memória para um usuário específico."""
        self.user = user
        logger.info(f"Módulo de Memória inicializado para usuário: {user.username}")

    def save_info(self, key, value, source="user", context=None):
        """Salva ou atualiza uma informação na memória.

        Args:
            key (str): A chave única para a informação.
            value (str): O valor da informação.
            source (str, optional): A origem da informação. Defaults to "user".
            context (str, optional): Contexto adicional. Defaults to None.

        Returns:
            bool: True se salvou com sucesso, False caso contrário.
        """
        if not key or not value:
            logger.error("Chave e valor não podem ser vazios.")
            return False

        key = key.strip().lower()  # Normaliza a chave

        try:
            memoria, created = MemoriaAssistente.objects.update_or_create(
                usuario=self.user,
                chave=key,
                defaults={"valor": value, "fonte": source, "data_atualizacao": timezone.now(), "ativo": True},
            )

            action = "criada" if created else "atualizada"
            logger.info(f"Informação {action} para a chave: '{key}'")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar informação para a chave '{key}': {e}")
            return False

    def get_info(self, key):
        """Recupera informação associada a uma chave.

        Args:
            key (str): A chave da informação a ser recuperada.

        Returns:
            dict: Um dicionário contendo os dados associados à chave,
                  ou None se a chave não for encontrada.
        """
        if not key:
            return None

        key = key.strip().lower()

        try:
            memoria = MemoriaAssistente.objects.get(usuario=self.user, chave=key, ativo=True)

            logger.info(f"Informação encontrada para a chave: '{key}'")
            return {
                "value": memoria.valor,
                "timestamp": memoria.data_criacao.isoformat(),
                "source": memoria.fonte,
                "updated": memoria.data_atualizacao.isoformat(),
            }

        except MemoriaAssistente.DoesNotExist:
            logger.info(f"Nenhuma informação encontrada para a chave: '{key}'")
            return None

        except Exception as e:
            logger.error(f"Erro ao buscar informação para a chave '{key}': {e}")
            return None

    def search_memories(self, query):
        """Busca memórias que contenham o termo especificado."""
        try:
            memorias = MemoriaAssistente.objects.filter(usuario=self.user, ativo=True).filter(
                models.Q(chave__icontains=query) | models.Q(valor__icontains=query)
            )[:10]  # Limita a 10 resultados

            results = []
            for memoria in memorias:
                results.append(
                    {
                        "key": memoria.chave,
                        "value": memoria.valor,
                        "timestamp": memoria.data_criacao.isoformat(),
                        "source": memoria.fonte,
                    }
                )

            logger.info(f"Encontradas {len(results)} memórias para a busca: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Erro ao buscar memórias com o termo '{query}': {e}")
            return []

    def get_recent_memories(self, limit=5):
        """Retorna as últimas N memórias salvas."""
        try:
            memorias = MemoriaAssistente.objects.filter(usuario=self.user, ativo=True).order_by("-data_atualizacao")[
                :limit
            ]

            results = []
            for memoria in memorias:
                results.append(
                    {
                        "key": memoria.chave,
                        "value": memoria.valor,
                        "timestamp": memoria.data_criacao.isoformat(),
                        "source": memoria.fonte,
                    }
                )

            logger.info(f"Retornadas {len(results)} memórias recentes")
            return results

        except Exception as e:
            logger.error(f"Erro ao buscar memórias recentes: {e}")
            return []

    def delete_memory(self, key):
        """Remove uma memória específica."""
        if not key:
            return False

        key = key.strip().lower()

        try:
            memoria = MemoriaAssistente.objects.get(usuario=self.user, chave=key, ativo=True)
            memoria.ativo = False
            memoria.save()

            logger.info(f"Memória removida para a chave: '{key}'")
            return True

        except MemoriaAssistente.DoesNotExist:
            logger.warning(f"Tentativa de remover memória inexistente: '{key}'")
            return False

        except Exception as e:
            logger.error(f"Erro ao remover memória para a chave '{key}': {e}")
            return False

    def clear_all_memories(self):
        """Remove todas as memórias do usuário."""
        try:
            count = MemoriaAssistente.objects.filter(usuario=self.user, ativo=True).update(ativo=False)

            logger.info(f"Removidas {count} memórias do usuário {self.user.username}")
            return count

        except Exception as e:
            logger.error(f"Erro ao limpar memórias: {e}")
            return 0

    def get_memory_stats(self):
        """Retorna estatísticas sobre as memórias do usuário."""
        try:
            total = MemoriaAssistente.objects.filter(usuario=self.user, ativo=True).count()

            by_source = (
                MemoriaAssistente.objects.filter(usuario=self.user, ativo=True)
                .values("fonte")
                .annotate(count=models.Count("fonte"))
            )

            return {"total_memories": total, "by_source": {item["fonte"]: item["count"] for item in by_source}}

        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de memória: {e}")
            return {"total_memories": 0, "by_source": {}}
