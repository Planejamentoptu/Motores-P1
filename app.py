from flask import Flask, render_template, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
import json

app = Flask(__name__)

# --- Autenticação com o Google usando variável de ambiente no Render ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials_info = os.environ.get("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_info)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

# --- ID da sua planilha ---
SHEET_ID = "1y9_GMOo04PDa8AzKbhba5ulJk18b7U9pFiTGriE2mEU"

# --- Função para acessar a planilha ---
def acessar_planilha():
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# --- INDEX: Consulta dinâmica ("/") ---
@app.route('/')
def index():
    return render_template("Consulta_Dados.html", dados=json.dumps(buscar_dados_planilha()))

# --- Rota auxiliar para carregar dados da planilha (JSON) ---
@app.route('/dados')
def dados():
    dados = buscar_dados_planilha()
    return jsonify(dados)

# --- Rota para receber filtros de busca via POST ---
@app.route('/buscar', methods=['POST'])
def buscar():
    filtros = request.get_json()
    dados = buscar_dados_planilha()
    resultados = []

    for linha in dados:
        if all(linha.get(chave, "").upper().startswith(str(filtros[chave]).upper()) if filtros[chave] else True for chave in filtros):
            resultados.append(linha)

    return jsonify(resultados)

# --- Função que busca os dados da aba CONSULTA_DADOS ---
def buscar_dados_planilha():
    planilha = acessar_planilha()
    intervalo = 'CONSULTA_DADOS!A:Q'
    resposta = planilha.values().get(spreadsheetId=SHEET_ID, range=intervalo).execute()
    valores = resposta.get('values', [])

    if not valores:
        return []

    cabecalhos = valores[0]
    dados = [dict(zip(cabecalhos, linha)) for linha in valores[1:] if len(linha) == len(cabecalhos)]
    return dados

# --- Rota do formulário de Reparo ---
@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    if request.method == 'POST':
        try:
            # Coleta os dados do formulário
            dados = request.form.to_dict()
            fabricante = dados['fabricante']
            if fabricante == 'OUTROS':
                fabricante = dados.get('campo3_outros', '')

            potencia = f"{dados['potencia']}{dados['unidade']}".upper()

            nova_linha = [
                dados['matricula'],
                fabricante,
                dados['tag'],
                dados['tensao'],
                potencia,
                dados['n_polos'],
                dados['carcaca'],
                dados['forma'],
                dados['criticidade'],
                dados['defeito'],
                dados['local'],
                dados['responsavel']
            ]

            planilha = acessar_planilha()
            planilha.values().append(
                spreadsheetId=SHEET_ID,
                range='DADOS_USUÁRIO!A:L',
                valueInputOption='RAW',
                body={'values': [nova_linha]}
            ).execute()

            return render_template("Reparo.html", message="✅ Dados inseridos com sucesso!")

        except Exception as e:
            return render_template("Reparo.html", message=f"❌ Erro ao inserir dados: {e}")
    return render_template("Reparo.html")

# --- Rota para movimentação de equipamentos ---
@app.route('/movimentacao', methods=['GET', 'POST'])
def movimentacao():
    if request.method == 'POST':
        try:
            dados = request.form.to_dict()
            nova_linha = [
                dados['tag_equipamento'],
                dados['matricula_saida'],
                dados['matricula_entrada'],
                dados['motivo'],
                dados['responsavel']
            ]

            planilha = acessar_planilha()
            planilha.values().append(
                spreadsheetId=SHEET_ID,
                range='DADOS_MOVIMENTACAO!A:E',
                valueInputOption='RAW',
                body={'values': [nova_linha]}
            ).execute()

            return render_template("Movimentacao.html", message="✅ Movimentação registrada com sucesso!")

        except Exception as e:
            return render_template("Movimentacao.html", message=f"❌ Erro ao registrar movimentação: {e}")
    return render_template("Movimentacao.html")

# --- Roda a aplicação localmente ---
if __name__ == '__main__':
    app.run(debug=True)
