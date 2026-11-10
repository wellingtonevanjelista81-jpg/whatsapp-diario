#!/usr/bin/env python3
"""
Envia uma mensagem diária (texto + imagem) para um grupo do WhatsApp,
usando dados de uma planilha pública do Google Sheets e a Green API.

Pensado para rodar no GitHub Actions (grátis, sem precisar de PC ligado):
todas as configurações vêm de variáveis de ambiente (Secrets do repositório).

NÃO precisa de conta de serviço, chave JSON ou qualquer credencial do
Google: a planilha precisa apenas estar com o compartilhamento
"Qualquer pessoa com o link" (modo Leitor), e o script lê os dados pelo
link público de exportação em CSV.

Como funciona:
1. Baixa a planilha em formato CSV (link público).
2. Procura a linha cujo valor na coluna "Data" bate com a data de hoje
   (formato DD/MM/AAAA).
3. Pega o texto (coluna "Mensagem") e a URL da imagem (coluna "ImagemURL")
   dessa linha.
4. Envia para o grupo via Green API (método sendFileByUrl, que baixa a
   imagem diretamente da URL informada).

Requisitos:
    pip install requests
"""

import csv
import datetime
import io
import os
import sys

import requests

# ====== CONFIGURAÇÃO — vem de variáveis de ambiente (Secrets) ======

# ID da planilha (está na URL: docs.google.com/spreadsheets/d/ESTE_ID/edit)
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]

# Nome da aba dentro da planilha
SHEET_NAME = os.environ.get("SHEET_NAME", "Página1")

# Nomes das colunas na planilha (precisam existir no cabeçalho, linha 1)
COL_DATA = "Data"          # formato DD/MM/AAAA
COL_MENSAGEM = "Mensagem"
COL_IMAGEM_URL = "ImagemURL"

# Dados da Green API
GREEN_API_ID_INSTANCE = os.environ["GREEN_API_ID_INSTANCE"]
GREEN_API_TOKEN_INSTANCE = os.environ["GREEN_API_TOKEN_INSTANCE"]

# Id do grupo no formato 1234567890-1234567890@g.us
GRUPO_CHAT_ID = os.environ["GRUPO_CHAT_ID"]

# ====================================================


def get_linha_de_hoje():
    """Baixa a planilha como CSV e busca a linha correspondente a hoje."""
    url_csv = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    )

    resp = requests.get(url_csv, timeout=30)
    resp.raise_for_status()

    # A planilha precisa estar compartilhada como "Qualquer pessoa com o link"
    if resp.text.strip().startswith("<"):
        raise RuntimeError(
            "Não consegui ler a planilha como CSV. Verifique se ela está "
            "compartilhada como 'Qualquer pessoa com o link - Leitor'."
        )

    leitor = csv.DictReader(io.StringIO(resp.text))
    hoje = datetime.date.today().strftime("%d/%m/%Y")

    for linha in leitor:
        if str(linha.get(COL_DATA, "")).strip() == hoje:
            return linha

    return None


def enviar_para_whatsapp(caption, imagem_url):
    """Envia a mensagem (texto + imagem) para o grupo via Green API."""
    endpoint = (
        f"https://api.green-api.com/waInstance{GREEN_API_ID_INSTANCE}"
        f"/sendFileByUrl/{GREEN_API_TOKEN_INSTANCE}"
    )

    nome_arquivo = imagem_url.split("/")[-1].split("?")[0] or "imagem.jpg"
    if "." not in nome_arquivo:
        nome_arquivo = "imagem.jpg"

    payload = {
        "chatId": GRUPO_CHAT_ID,
        "urlFile": imagem_url,
        "fileName": nome_arquivo,
        "caption": caption,
    }

    resp = requests.post(endpoint, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    linha = get_linha_de_hoje()

    if linha is None:
        print("Nenhuma linha encontrada para a data de hoje. Nada a enviar.")
        sys.exit(0)

    mensagem = linha.get(COL_MENSAGEM, "")
    imagem_url = linha.get(COL_IMAGEM_URL, "")

    if not imagem_url:
        print("Linha de hoje encontrada, mas sem URL de imagem. Abortando.")
        sys.exit(1)

    print(f"Enviando mensagem de hoje: {mensagem[:60]}...")
    resultado = enviar_para_whatsapp(mensagem, imagem_url)

    print("Enviado com sucesso:", resultado)


if __name__ == "__main__":
    main()
