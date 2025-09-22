from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import ConviteUsuario, PerfilUsuarioEstendido, PermissaoPersonalizada, StatusUsuario, TipoUsuario

try:
    from funcionarios.models import Funcionario
except Exception:  # módulo pode não existir no setup mínimo de testes
    Funcionario = None

User = get_user_model()


class UsuarioCreateForm(UserCreationForm):
    """Formulário para criação de usuários com perfil estendido"""

    # Campos do User
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")

    # Campos do PerfilUsuarioEstendido
    avatar = forms.ImageField(
        required=False, label="Foto do Perfil", help_text="Imagem para o avatar do usuário (PNG, JPG, máx. 5MB)"
    )
    tipo_usuario = forms.ChoiceField(choices=TipoUsuario.choices, required=True, label="Tipo de Usuário")
    cpf = forms.CharField(
        max_length=14, required=False, label="CPF", widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"})
    )
    telefone = forms.CharField(max_length=20, required=False, label="Telefone")
    celular = forms.CharField(max_length=20, required=False, label="Celular")
    cargo = forms.CharField(max_length=100, required=False, label="Cargo")
    departamento = forms.CharField(max_length=100, required=False, label="Departamento")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")  # Removido password1 e password2

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Limitar as opções de tipo de usuário
        if self.request_user and not self.request_user.is_superuser:
            # Admin de empresa não pode criar super_admin ou outro admin_empresa
            self.fields["tipo_usuario"].choices = [
                (k, v) for k, v in TipoUsuario.choices if k not in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN_EMPRESA]
            ]

        # Adicionar classes CSS
        for _field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está em uso.")
        return email

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if cpf and PerfilUsuarioEstendido.objects.filter(cpf=cpf).exists():
            raise ValidationError("Este CPF já está cadastrado.")
        return cpf

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        if commit:
            user.save()
            # Garantir criação ou obtenção do perfil (signal deve criar; fallback por segurança)
            perfil, created = PerfilUsuarioEstendido.objects.get_or_create(
                user=user,
                defaults={
                    "tipo_usuario": self.cleaned_data["tipo_usuario"],
                    "cpf": self.cleaned_data.get("cpf"),
                    "telefone": self.cleaned_data.get("telefone"),
                    "celular": self.cleaned_data.get("celular"),
                    "cargo": self.cleaned_data.get("cargo"),
                    "departamento": self.cleaned_data.get("departamento"),
                    "status": StatusUsuario.ATIVO,
                    "criado_por": self.request_user,
                },
            )
            # Atualizar campos caso perfil já existisse (ex: convite + criação manual)
            if not created:
                campos_update = ["tipo_usuario", "cpf", "telefone", "celular", "cargo", "departamento"]
                alterado = False
                for campo in campos_update:
                    novo_valor = self.cleaned_data.get(campo)
                    if novo_valor and getattr(perfil, campo) != novo_valor:
                        setattr(perfil, campo, novo_valor)
                        alterado = True
                if perfil.status != StatusUsuario.ATIVO:
                    perfil.status = StatusUsuario.ATIVO
                    alterado = True
                if alterado:
                    perfil.save()

            # Associar usuário ao tenant via TenantUser se tenant fornecido
            if self.tenant:
                try:
                    from core.models import TenantUser

                    TenantUser.objects.get_or_create(tenant=self.tenant, user=user)
                except Exception:
                    # Fallback silencioso para evitar quebrar criação se modelo mudar
                    pass

        return user


class UsuarioUpdateForm(forms.ModelForm):
    """Formulário para atualização de usuários"""

    # Campos do User
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")
    is_active = forms.BooleanField(required=False, label="Usuário Ativo")
    is_staff = forms.BooleanField(required=False, label="Acesso Staff")
    is_superuser = forms.BooleanField(required=False, label="Superusuário")

    class Meta:
        model = PerfilUsuarioEstendido
        fields = [
            "avatar",
            "tipo_usuario",
            "status",
            "cpf",
            "rg",
            "data_nascimento",
            "telefone",
            "celular",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "cep",
            "cargo",
            "departamento",
            "data_admissao",
            "salario",
            "autenticacao_dois_fatores",
            "receber_email_notificacoes",
            "receber_sms_notificacoes",
            "receber_push_notificacoes",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "data_admissao": forms.DateInput(attrs={"type": "date"}),
            "salario": forms.NumberInput(attrs={"step": "0.01"}),
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Preencher campos do User
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["is_active"].initial = self.instance.user.is_active
            self.fields["is_staff"].initial = self.instance.user.is_staff
            self.fields["is_superuser"].initial = self.instance.user.is_superuser

        # Limitar as opções de tipo de usuário
        if self.request_user and not self.request_user.is_superuser:
            self.fields["tipo_usuario"].choices = [
                (k, v) for k, v in TipoUsuario.choices if k not in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN_EMPRESA]
            ]
            # Impede que um admin de empresa edite um usuário para um tipo que ele não pode gerenciar
            if self.instance.tipo_usuario in [TipoUsuario.SUPER_ADMIN, TipoUsuario.ADMIN_EMPRESA]:
                self.fields["tipo_usuario"].disabled = True

        # Adicionar classes CSS
        for _field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
        # Gating: somente superuser pode editar is_staff/is_superuser; para outros desabilitar
        if not (self.request_user and self.request_user.is_superuser):
            for fname in ["is_staff", "is_superuser"]:
                if fname in self.fields:
                    self.fields[fname].disabled = True

        # Read-only cargo/salario se houver vínculo Funcionario
        if Funcionario and self.instance and getattr(self.instance, "user", None):
            try:
                if Funcionario.objects.filter(user=self.instance.user).exists():
                    for fname in ["cargo", "salario"]:
                        if fname in self.fields:
                            self.fields[fname].disabled = True
            except Exception:
                pass

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
            raise ValidationError("Este e-mail já está em uso.")
        return email

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if cpf and PerfilUsuarioEstendido.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este CPF já está cadastrado.")
        return cpf

    def save(self, commit=True):
        perfil = super().save(commit=False)

        # Atualizar campos do User
        user = perfil.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.is_active = self.cleaned_data["is_active"]
        # Atualizar flags de privilégio somente se superuser
        if self.request_user and self.request_user.is_superuser:
            user.is_staff = self.cleaned_data.get("is_staff", user.is_staff)
            user.is_superuser = self.cleaned_data.get("is_superuser", user.is_superuser)

        if commit:
            user.save()
            perfil.save()

        return perfil


class ConviteUsuarioForm(forms.ModelForm):
    """Formulário para envio de convites"""

    class Meta:
        model = ConviteUsuario
        fields = ["email", "tipo_usuario", "nome_completo", "cargo", "departamento", "mensagem_personalizada"]
        widgets = {
            "mensagem_personalizada": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        # Adicionar classes CSS
        for _field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"]

        # Verificar se já existe usuário com este email
        if User.objects.filter(email=email).exists():
            raise ValidationError("Já existe um usuário cadastrado com este e-mail.")

        # Verificar se já existe convite pendente
        if ConviteUsuario.objects.filter(email=email, usado=False, tenant=self.tenant).exists():
            raise ValidationError("Já existe um convite pendente para este e-mail neste tenant.")

        return email

    def save(self, commit=True):
        convite = super().save(commit=False)

        # Definir data de expiração (7 dias)
        convite.expirado_em = timezone.now() + timedelta(days=7)
        convite.enviado_por = self.request_user
        convite.tenant = self.tenant

        if commit:
            convite.save()

        return convite


class PermissaoPersonalizadaForm(forms.ModelForm):
    """Formulário para gerenciar permissões personalizadas"""

    class Meta:
        model = PermissaoPersonalizada
        fields = ["user", "scope_tenant", "modulo", "acao", "recurso", "concedida", "data_expiracao", "observacoes"]
        widgets = {
            "data_expiracao": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Campo scope_tenant opcional (quando não informado => permissão global)
        if "scope_tenant" in self.fields:
            from core.models import Tenant

            if self.tenant:
                # Limita escolha ao tenant atual (consistente com contexto)
                self.fields["scope_tenant"].queryset = Tenant.objects.filter(pk=self.tenant.pk)
                self.fields["scope_tenant"].initial = self.tenant
            else:
                self.fields["scope_tenant"].queryset = Tenant.objects.all()
                self.fields["scope_tenant"].required = False

        # Filtrar usuários pelo tenant atual ou todos se superuser sem tenant ativo
        if self.tenant:
            self.fields["user"].queryset = self.tenant.user_set.all()
        else:
            self.fields["user"].queryset = User.objects.all()

        # Adicionar classes CSS
        for _field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "form-control"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        # Evitar duplicados: se já existir permissão igual, bloquear criação
        user = data.get("user")
        modulo = data.get("modulo")
        acao = data.get("acao")
        recurso = data.get("recurso") or None
        scope_tenant = data.get("scope_tenant") or None
        if user and modulo and acao:
            qs = PermissaoPersonalizada.objects.filter(
                user=user, modulo=modulo, acao=acao, recurso=recurso, scope_tenant=scope_tenant
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(None, "Já existe uma permissão com estes parâmetros (mesmo escopo).")
        return data
        return data


class FiltroUsuarioForm(forms.Form):
    """Formulário para filtrar usuários"""

    busca = forms.CharField(
        max_length=100,
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Nome, email, CPF...", "class": "form-control"}),
    )

    tipo_usuario = forms.ChoiceField(
        choices=[("", "Todos os tipos")] + list(TipoUsuario.choices),
        required=False,
        label="Tipo de Usuário",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(StatusUsuario.choices),
        required=False,
        label="Status",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    departamento = forms.CharField(
        max_length=100,
        required=False,
        label="Departamento",
        widget=forms.TextInput(attrs={"placeholder": "Departamento...", "class": "form-control"}),
    )

    ativo = forms.ChoiceField(
        choices=[("", "Todos"), ("true", "Ativos"), ("false", "Inativos")],
        required=False,
        label="Usuário Ativo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class MeuPerfilForm(forms.ModelForm):
    """Formulário para o usuário editar seu próprio perfil"""

    # Campos do User
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")

    class Meta:
        model = PerfilUsuarioEstendido
        fields = [
            "avatar",
            "cpf",
            "rg",
            "data_nascimento",
            "telefone",
            "celular",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "cep",
            "cargo",
            "departamento",
            "receber_email_notificacoes",
            "receber_sms_notificacoes",
            "receber_push_notificacoes",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Preencher campos do User
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

        # CPF somente leitura se já definido (permitir primeiro cadastro caso vazio)
        if self.instance and self.instance.cpf:
            self.fields["cpf"].widget.attrs["readonly"] = True
        else:
            self.fields["cpf"].widget.attrs["placeholder"] = "XXX.XXX.XXX-XX"

    def save(self, commit=True):
        """Salva tanto o User quanto o PerfilUsuarioEstendido"""
        perfil = super().save(commit=False)

        # Atualizar campos do User
        if perfil.user:
            perfil.user.first_name = self.cleaned_data["first_name"]
            perfil.user.last_name = self.cleaned_data["last_name"]
            perfil.user.email = self.cleaned_data["email"]
            if commit:
                perfil.user.save()

        if commit:
            perfil.save()

        return perfil
