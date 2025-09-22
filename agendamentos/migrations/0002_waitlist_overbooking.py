from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ("agendamentos", "0001_initial"),
        ("clientes", "0002_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Data de criação")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Data de atualização")),
                ("prioridade", models.PositiveIntegerField(default=100)),
                ("status", models.CharField(default="ATIVO", max_length=20)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist_entries", to="clientes.cliente")),
                ("slot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist", to="agendamentos.slot")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist_entries", to="core.tenant")),
            ],
            options={
                "ordering": ["prioridade", "created_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="waitlistentry",
            unique_together={("slot", "cliente")},
        ),
    ]
