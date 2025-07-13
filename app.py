from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
import json
import mimetypes
import io
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

# --- Autenticação Google ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials_info = os.environ.get("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_info)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

# --- IDs ---
SHEET_ID = "1y9_GMOo04PDa8AzKbhba5ulJk18b7U9pFiTGriE2mEU"
DRIVE_FOLDER_ID = "1IC-Gn8AzcQ3O5J3Lcx-90vasdk1wsu1n"  # Pasta no Google Drive

# --- Planilha ---
def acessar_planilha():
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

# --- Upload da imagem para o Drive ---
def enviar_imagem_drive(imagem):
    service = build('drive', 'v3', credentials=creds)
    nome_arquivo = secure_filename(imagem.filename)
    mimetype = mimetypes.guess_type(nome_arquivo)[0] or 'application/octet-stream'

    media = MediaIoBaseUpload(imagem.stream, mimetype=mimetype, resumable=True)
    arquivo = service.files().create(
        body={
            'name': nome_arquivo,
            'parents': [DRIVE_FOLDER_ID],
            'mimeType': mimetype
        },
        media_body=media,
        fields='id'
    ).execute()

    file_id = arquivo.get('id')
    # Torna o arquivo público
    service.permissions().create(
        fileId=file_id,
        body={'role': 'reader', 'type': 'anyone'},
    ).execute()

    return f"https://drive.google.com/uc?id={file_id}"

# --- Página principal ---
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
    resultados = []

    for linha in dados:
        if all(linha.get(chave, "").upper().startswith(str(filtros[chave]).upper()) if filtros[chave] else True for chave in filtros):
            resultados.append(linha)
    return jsonify(resultados)

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

# --- Formulário de Reparo ---
@app.route('/reparo', methods=['GET', 'POST'])
def Reparo():
    message = None
    if request.method == 'POST':
        try:
            # Coleta dados do formulário
            form = request.form
            imagem = request.files.get('imagem')

            fabricante = form.get('fabricante', '').strip()
            campo3_outros = form.get('campo3_outros', '').strip()
            fabricante_final = campo3_outros if fabricante == "OUTROS" else fabricante

            url_imagem = ''
            if imagem and imagem.filename:
                url_imagem = enviar_imagem_drive(imagem)

            nova_linha = [
                form.get('matricula', '').strip(),
                fabricante_final,
                form.get('tag', '').strip(),
                form.get('tensao', '').strip(),
                f"{form.get('potencia', '').strip()} {form.get('unidade', '').strip()}",
                form.get('n_polos', '').strip(),
                form.get('carcaca', '').strip(),
                form.get('forma', '').strip(),
                form.get('criticidade', '').strip(),
                form.get('defeito', '').strip(),
                form.get('local', '').strip(),
                form.get('responsavel', '').strip(),
                url_imagem
            ]

            acessar_planilha().values().append(
                spreadsheetId=SHEET_ID,
                range='DADOS_REPARO!A:M',
                valueInputOption='RAW',
                body={'values': [nova_linha]}
            ).execute()

            message = "✅ Dados inseridos com sucesso!"
        except Exception as e:
            message = f"❌ Erro ao inserir dados: {str(e)}"
    return render_template("Reparo.html", message=message)

# --- Página de Movimentação ---
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

            acessar_planilha().values().append(
                spreadsheetId=SHEET_ID,
                range='DADOS_MOVIMENTACAO!A:E',
                valueInputOption='RAW',
                body={'values': [nova_linha]}
            ).execute()

            return render_template("Movimentacao.html", message="✅ Movimentação registrada com sucesso!")
        except Exception as e:
            return render_template("Movimentacao.html", message=f"❌ Erro ao registrar movimentação: {e}")
    return render_template("Movimentacao.html")

# --- Roda localmente ---
if __name__ == '__main__':
    app.run(debug=True)
