from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),  # assumindo que tenants existem na 0001 de core
        ("portal_cliente", "0002_documentoportalcliente"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalClienteConfiguracao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Data de criação")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Data de atualização")),
                ("checkin_antecedencia_min", models.PositiveIntegerField(default=30)),
                ("checkin_tolerancia_pos_min", models.PositiveIntegerField(default=60)),
                ("finalizacao_tolerancia_horas", models.PositiveIntegerField(default=6)),
                ("cancelamento_limite_horas", models.PositiveIntegerField(default=24)),
                ("throttle_checkin", models.PositiveIntegerField(default=12)),
                ("throttle_finalizar", models.PositiveIntegerField(default=10)),
                ("throttle_avaliar", models.PositiveIntegerField(default=10)),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_config",
                        to="core.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Config Portal Cliente",
                "verbose_name_plural": "Configs Portal Cliente",
            },
        ),
    ]
