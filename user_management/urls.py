from django.urls import path

from . import views

app_name = "user_management"

urlpatterns = [
    # Dashboard
    path("home/", views.user_management_home, name="user_management_home"),
    # Usuários
    path("", views.UsuarioListView.as_view(), name="usuario_list"),  # Dashboard padrão será a lista de usuários
    path("usuarios/", views.UsuarioListView.as_view(), name="dashboard"),  # Mantém compatibilidade
    path("usuarios/criar/", views.UsuarioCreateView.as_view(), name="usuario_create"),
    path("usuarios/<int:pk>/", views.UsuarioDetailView.as_view(), name="usuario_detail"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_update"),
    path("usuarios/<int:pk>/excluir/", views.UsuarioDeleteView.as_view(), name="usuario_delete"),
    # Convites
    path("convites/", views.ConviteListView.as_view(), name="convite_list"),
    path("convites/criar/", views.ConviteCreateView.as_view(), name="convite_create"),
    path("convites/aceitar/<uuid:token>/", views.AceitarConviteView.as_view(), name="aceitar_convite"),
    # Permissões
    path("permissoes/", views.PermissaoListView.as_view(), name="permissao_list"),
    path("permissoes/criar/", views.PermissaoCreateView.as_view(), name="permissao_create"),
    # Logs e Sessões
    path("atividades/", views.LogAtividadeListView.as_view(), name="atividade_list"),
    path("sessoes/", views.SessaoUsuarioListView.as_view(), name="sessao_list"),
    path("sessoes/<int:pk>/encerrar/", views.SessaoEncerrarView.as_view(), name="sessao_encerrar"),
    path("sessoes/<int:pk>/detalhe/", views.SessaoDetalheView.as_view(), name="sessao_detalhe"),
    path(
        "sessoes/usuario/<int:user_id>/encerrar-todas/",
        views.SessaoEncerrarTodasView.as_view(),
        name="sessao_encerrar_todas",
    ),
    path("sessoes/encerrar-multiplas/", views.SessaoEncerrarMultiplasView.as_view(), name="sessao_encerrar_multiplas"),
    path("api/sessoes/", views.SessaoUsuarioApiView.as_view(), name="sessao_api"),
    # Perfil Pessoal
    path("meu-perfil/", views.MeuPerfilView.as_view(), name="meu_perfil"),
    path("alterar-senha/", views.ChangePasswordView.as_view(), name="change_password"),
    path("usuarios/<int:pk>/toggle-2fa/", views.ToggleTwoFactorView.as_view(), name="toggle_2fa"),
    # 2FA API
    path("2fa/setup/", views.TwoFASetupView.as_view(), name="2fa_setup"),
    path("2fa/confirm/", views.TwoFAConfirmView.as_view(), name="2fa_confirm"),
    path("2fa/disable/", views.TwoFADisableView.as_view(), name="2fa_disable"),
    path("2fa/verify/", views.TwoFAVerifyView.as_view(), name="2fa_verify"),
    path("2fa/challenge/", views.TwoFAChallengeView.as_view(), name="2fa_challenge"),
    path("2fa/regenerate/", views.TwoFARegenerateCodesView.as_view(), name="2fa_regenerate_codes"),
    path("2fa/admin-reset/", views.TwoFAAdminResetView.as_view(), name="2fa_admin_reset"),
    path("2fa/admin-force-regenerate/", views.TwoFAAdminForceRegenerateView.as_view(), name="2fa_admin_force_regen"),
    path("2fa/metrics-dashboard/", views.TwoFAMetricsDashboardView.as_view(), name="2fa_metrics_dashboard"),
    path("2fa/metrics.json", views.TwoFAMetricsJSONView.as_view(), name="2fa_metrics_json"),
]
