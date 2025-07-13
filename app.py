from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
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

def acessar_planilha():
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# --- Consulta dinâmica ---
@app.route('/')
def index():
    return render_template("Consulta_Dados.html", dados=json.dumps(buscar_dados_planilha()))

@app.route('/dados')
def dados():
    return jsonify(buscar_dados_planilha())

@app.route('/buscar', methods=['POST'])
def buscar():
    filtros = request.get_json()
    dados = buscar_dados_planilha()
    resultados = [
        linha for linha in dados
        if all(linha.get(k, "").upper().startswith(str(filtros[k]).upper()) if filtros[k] else True for k in filtros)
    ]
    return jsonify(resultados)

def buscar_dados_planilha():
    planilha = acessar_planilha()
    intervalo = 'CONSULTA_DADOS!A:Q'
    resposta = planilha.values().get(spreadsheetId=SHEET_ID, range=intervalo).execute()
    valores = resposta.get('values', [])
    if not valores:
        return []
    cabecalhos = valores[0]
    return [dict(zip(cabecalhos, linha)) for linha in valores[1:] if len(linha) == len(cabecalhos)]

# --- Reparo (corrigido nome da função e leitura de todos os campos) ---
@app.route('/reparo', methods=['GET', 'POST'])
def reparo():
    message = None
    if request.method == 'POST':
        try:
            # Coleta dos dados do formulário
            dados = request.form.to_dict()
            fabricante = dados.get('fabricante', '').strip()
            outros = dados.get('campo3_outros', '').strip()
            fabricante_final = outros if fabricante == "OUTROS" else fabricante

            imagem = request.files.get('imagem')
            url_imagem = ''
            if imagem and imagem.filename != '':
                filename = secure_filename(imagem.filename)
                filepath = os.path.join('static/uploads', filename)
                imagem.save(filepath)
                url_imagem = f"/static/uploads/{filename}"

            # Monta a linha com todos os campos
            nova_linha = [
                dados.get('matricula', ''),
                fabricante_final,
                dados.get('tag', ''),
                dados.get('tensao', ''),
                f"{dados.get('potencia', '')} {dados.get('unidade', '')}",
                dados.get('n_polos', ''),
                dados.get('carcaca', ''),
                dados.get('forma', ''),
                dados.get('criticidade', ''),
                dados.get('defeito', ''),
                dados.get('local', ''),
                dados.get('responsavel', ''),
                url_imagem
            ]

            planilha = acessar_planilha()
            planilha.values().append(
                spreadsheetId=SHEET_ID,
                range='DADOS_REPARO!A:M',
                valueInputOption='RAW',
                body={'values': [nova_linha]}
            ).execute()

            message = "✅ Dados inseridos com sucesso!"

        except Exception as e:
            message = f"❌ Erro ao inserir dados: {str(e)}"

    return render_template("Reparo.html", message=message)

# --- Movimentação ---
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

if __name__ == '__main__':
    app.run(debug=True)
