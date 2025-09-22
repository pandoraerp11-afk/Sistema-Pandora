from django.db import models

from core.models import Tenant
from prontuarios.models import AtendimentoSlot

from .models import Slot


class SlotLegacyMap(models.Model):
    """Mapeia relacionamento entre AtendimentoSlot legado e Slot novo.
    Usado para backfill e consultas cruzadas durante a fase de migração.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="slot_legacy_maps")
    legacy_slot = models.OneToOneField(AtendimentoSlot, on_delete=models.CASCADE, related_name="map_novo_slot")
    novo_slot = models.OneToOneField(Slot, on_delete=models.CASCADE, related_name="map_legacy_slot")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mapeamento Slot Legado"
        verbose_name_plural = "Mapeamentos Slots Legados"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "legacy_slot", "novo_slot"], name="unique_slot_map_triplo")
        ]

    def __str__(self):
        return f"Map legacy {self.legacy_slot_id} -> novo {self.novo_slot_id}"
