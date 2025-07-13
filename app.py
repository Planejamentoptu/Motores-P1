from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import json
import tempfile

app = Flask(__name__)

# --- Autenticação Google com variável de ambiente ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials_info = os.environ.get("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(credentials_info)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

SHEET_ID = "1y9_GMOo04PDa8AzKbhba5ulJk18b7U9pFiTGriE2mEU"
DRIVE_FOLDER_ID = "1IC-Gn8AzcQ3O5J3Lcx-90vasdk1wsu1n"

def acessar_planilha():
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

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

@app.route('/')
def index():
    return render_template("Consulta_Dados.html", dados=json.dumps(buscar_dados_planilha()))

@app.route('/dados')
def dados():
    dados = buscar_dados_planilha()
    return jsonify(dados)

@app.route('/buscar', methods=['POST'])
def buscar():
    filtros = request.get_json()
    dados = buscar_dados_planilha()
    resultados = []

    for linha in dados:
        if all(linha.get(chave, "").upper().startswith(str(filtros[chave]).upper()) if filtros[chave] else True for chave in filtros):
            resultados.append(linha)

    return jsonify(resultados)

@app.route('/reparo', methods=['GET', 'POST'])
def Reparo():
    message = None
    if request.method == 'POST':
        try:
            # Dados do formulário
            matricula = request.form.get('matricula', '').strip()
            fabricante = request.form.get('fabricante', '').strip()
            campo3_outros = request.form.get('campo3_outros', '').strip()
            tag = request.form.get('tag', '').strip()
            tensao = request.form.get('tensao', '').strip()
            potencia = request.form.get('potencia', '').strip()
            unidade = request.form.get('unidade', '').strip()
            n_polos = request.form.get('n_polos', '').strip()
            carcaca = request.form.get('carcaca', '').strip()
            forma = request.form.get('forma', '').strip()
            criticidade = request.form.get('criticidade', '').strip()
            defeito = request.form.get('defeito', '').strip()
            local = request.form.get('local', '').strip()
            responsavel = request.form.get('responsavel', '').strip()
            imagem = request.files.get('imagem')

            fabricante_final = campo3_outros if fabricante == "OUTROS" else fabricante

            # Upload da imagem para o Drive
            url_imagem = ''
            if imagem and imagem.filename:
                filename = secure_filename(imagem.filename)
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    imagem.save(temp_file.name)
                    media = MediaFileUpload(temp_file.name, mimetype='image/jpeg')
                    drive_service = build('drive', 'v3', credentials=creds)
                    file_metadata = {
                        'name': filename,
                        'parents': [DRIVE_FOLDER_ID]
                    }
                    uploaded_file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    file_id = uploaded_file.get('id')

                    # Tornar imagem pública
                    drive_service.permissions().create(
                        fileId=file_id,
                        body={'role': 'reader', 'type': 'anyone'},
                    ).execute()

                    url_imagem = f"https://drive.google.com/uc?id={file_id}"

            # Linha a ser enviada para planilha
            nova_linha = [
                matricula, fabricante_final, tag, tensao,
                f"{potencia} {unidade}", n_polos, carcaca, forma,
                criticidade, defeito, local, responsavel, url_imagem
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

    return render_template('Reparo.html', message=message)

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

if __name__ == '__main__':
    app.run(debug=True)
