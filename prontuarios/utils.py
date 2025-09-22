import io
import os
import uuid
from datetime import timedelta

from django.utils import timezone
from PIL import Image


def upload_cliente_foto(instance, filename):
    """Novo caminho para fotos vinculadas a Cliente (substitui pacientes)."""
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("prontuarios", "clientes", str(instance.tenant.id), filename)


def upload_foto_evolucao(instance, filename):
    """Caminho de fotos de evolução agora baseado em cliente."""
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    # Usa cliente associado
    return os.path.join("prontuarios", "evolucao", str(instance.cliente.tenant.id), str(instance.cliente.id), filename)


def redimensionar_imagem(imagem, max_width=800, max_height=600, quality=85):
    """
    Redimensiona uma imagem mantendo a proporção.

    Args:
        imagem: Arquivo de imagem
        max_width: Largura máxima
        max_height: Altura máxima
        quality: Qualidade da compressão (1-100)

    Returns:
        Arquivo de imagem redimensionado
    """
    try:
        img = Image.open(imagem)

        # Converter para RGB se necessário
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        # Calcular novo tamanho mantendo proporção
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Salvar em buffer
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)

        return output
    except Exception:
        # Em caso de erro, retornar imagem original
        return imagem


# gerar_numero_prontuario removido (era específico de Paciente).


def calcular_idade(data_nascimento):
    """
    Calcula a idade com base na data de nascimento.

    Args:
        data_nascimento: Data de nascimento

    Returns:
        Idade em anos
    """
    if not data_nascimento:
        return None

    hoje = timezone.now().date()
    idade = hoje.year - data_nascimento.year

    # Ajustar se ainda não fez aniversário este ano
    if hoje < data_nascimento.replace(year=hoje.year):
        idade -= 1

    return idade


def validar_cpf(cpf):
    """
    Valida um CPF brasileiro.

    Args:
        cpf: String com o CPF

    Returns:
        Boolean indicando se o CPF é válido
    """
    # Remove caracteres não numéricos
    cpf = "".join(filter(str.isdigit, cpf))

    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return False

    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False

    # Calcula o primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    # Verifica o primeiro dígito
    if int(cpf[9]) != digito1:
        return False

    # Calcula o segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    # Verifica o segundo dígito
    return int(cpf[10]) == digito2


def formatar_cpf(cpf):
    """
    Formata um CPF para exibição.

    Args:
        cpf: String com o CPF

    Returns:
        CPF formatado (XXX.XXX.XXX-XX)
    """
    if not cpf:
        return ""

    # Remove caracteres não numéricos
    cpf = "".join(filter(str.isdigit, cpf))

    if len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

    return cpf


def formatar_telefone(telefone):
    """
    Formata um telefone para exibição.

    Args:
        telefone: String com o telefone

    Returns:
        Telefone formatado
    """
    if not telefone:
        return ""

    # Remove caracteres não numéricos
    telefone = "".join(filter(str.isdigit, telefone))

    if len(telefone) == 11:  # Celular com DDD
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    elif len(telefone) == 10:  # Fixo com DDD
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"

    return telefone


def calcular_proximo_atendimento(ultimo_atendimento, servico):
    """
    Calcula a data sugerida para o próximo atendimento.

    Args:
        ultimo_atendimento: Data do último atendimento
    servico: Instância de Servico (ou perfil clínico via servico.perfil_clinico)

    Returns:
        Data sugerida para o próximo atendimento
    """
    intervalo = getattr(getattr(servico, "perfil_clinico", None), "intervalo_minimo_sessoes", None)
    if not ultimo_atendimento or not intervalo:
        return None

    return ultimo_atendimento + timedelta(days=intervalo)


def gerar_relatorio_cliente(cliente):
    """Relatório simplificado para Cliente (substitui gerar_relatorio_paciente)."""
    from .models import Atendimento, FotoEvolucao

    atendimentos = Atendimento.objects.filter(cliente=cliente).order_by("-data_atendimento")
    fotos = FotoEvolucao.objects.filter(cliente=cliente).order_by("-data_foto")
    # Anamnese não tem cliente direto; pode ser ligada via atendimento ou futuro perfil clínico
    return {
        "cliente": cliente,
        "total_atendimentos": atendimentos.count(),
        "ultimo_atendimento": atendimentos.first(),
        # Compat: chave antiga mantém nome, mas agora usando servico.nome_servico
        "procedimentos_realizados": atendimentos.values_list("servico__nome_servico", flat=True).distinct(),
        "total_fotos": fotos.count(),
        "fotos_recentes": fotos[:5],
    }


def verificar_contraindicacoes_cliente(cliente, servico):
    """
    Verifica se há contraindicações para um serviço clínico específico.

    Args:
        cliente: Instância de Cliente
        servico: Instância de Servico

    Returns:
        Lista de strings com contraindicações encontradas
    """

    contraindicacoes = []

    # Buscar anamnese mais recente
    # Placeholder: ligar a perfil clínico ou anamneses via cliente futuramente
    anamnese = None

    if not anamnese:
        contraindicacoes.append("Cliente sem anamnese registrada")
        return contraindicacoes

    # Verificações básicas (podem ser expandidas conforme necessário)
    perfil = getattr(servico, "perfil_clinico", None)
    contra = (getattr(perfil, "contraindicacoes", "") or "").lower()
    if anamnese.gestante and "gestante" in contra:
        contraindicacoes.append("Cliente gestante")

    if anamnese.amamentando and "amamentação" in contra:
        contraindicacoes.append("Cliente em período de amamentação")

    if anamnese.uso_medicamentos and "medicamento" in contra:
        contraindicacoes.append("Cliente em uso de medicamentos")

    return contraindicacoes


# backup_dados_paciente removido.
