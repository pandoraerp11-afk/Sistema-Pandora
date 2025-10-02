from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_role_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="dadosbancarios",
            name="titular",
            field=models.CharField(default="TITULAR", max_length=100, verbose_name="Titular da Conta"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dadosbancarios",
            name="documento_titular",
            field=models.CharField(default="00000000000", max_length=20, verbose_name="CPF/CNPJ do Titular"),
            preserve_default=False,
        ),
    ]
