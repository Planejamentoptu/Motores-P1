from flask import Flask, render_template, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json, os, time
from werkzeug.utils import secure_filename


app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = "1y9_GMOo04PDa8AzKbhba5ulJk18b7U9pFiTGriE2mEU"
CACHE_FILE = "cache.json"
CACHE_EXPIRACAO = 600  # 10 minutos

creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

def carregar_dados_cache():
    if os.path.exists(CACHE_FILE):
        tempo_modificado = os.path.getmtime(CACHE_FILE)
        if time.time() - tempo_modificado < CACHE_EXPIRACAO:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None

def salvar_dados_cache(dados):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False)

def buscar_dados_planilha():
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="'CONSULTA_DADOS'!A:Q").execute()
    values = result.get('values', [])
    
    if not values:
        return []

    headers = values[0]
    dados = [
        {headers[i]: linha[i] if i < len(linha) else '' for i in range(len(headers))}
        for linha in values[1:]
    ]
    return dados

@app.route('/')
def Consulta_Dados():
    try:
        # Força atualização da planilha a cada atualização da página
        dados = buscar_dados_planilha()
        salvar_dados_cache(dados)
    except Exception as e:
        print(f"Erro ao buscar dados da planilha: {e}")
        # Em caso de erro, tenta usar cache
        dados = carregar_dados_cache()
        if dados is None:
            dados = []

    return render_template('Consulta_Dados.html', dados=json.dumps(dados))

@app.route('/buscar', methods=['POST'])
def buscar():
    dados_filtros = request.get_json()
    dados = carregar_dados_cache()
    if dados is None:
        dados = buscar_dados_planilha()
        salvar_dados_cache(dados)

    dados_filtrados = []
    for linha in dados:
        corresponde = True
        for campo, valor in dados_filtros.items():
            if valor and not linha.get(campo.upper(), '').upper().startswith(valor.upper()):
                corresponde = False
                break
        if corresponde:
            dados_filtrados.append(linha)

    return jsonify(dados_filtrados)

@app.route('/adicionar', methods=['GET', 'POST'])
def Reparo():
    mensagem = ''
    if request.method == 'POST':
        try:
            dados = request.form.to_dict()

            # --- Upload de imagem ---
            imagem = request.files.get('imagem')
            nome_imagem = ''
            if imagem and imagem.filename:
                extensao = imagem.filename.rsplit('.', 1)[-1].lower()
                nome_imagem = f"{int(time.time())}_{dados.get('matricula', '').replace(' ', '_')}.{extensao}"
                caminho = os.path.join('static', 'uploads', nome_imagem)
                imagem.save(caminho)

            # --- Dados da planilha ---
            valores = [
                dados.get('matricula', ''),
                dados.get('fabricante', '') if dados.get('fabricante') != 'OUTROS' else dados.get('campo3_outros', ''),
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
                f"http://127.0.0.1:5000/static/uploads/{nome_imagem}" if nome_imagem else ''
            ]

            service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="'DADOS_REPARO'!A:M",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [valores]}
            ).execute()

            mensagem = '✅ Dados enviados com sucesso!'

        except Exception as e:
            mensagem = f'❌ Erro ao enviar dados: {str(e)}'

    return render_template('Reparo.html', message=mensagem)


@app.route('/movimentacao', methods=['GET', 'POST'])
def movimentacao():
    mensagem = ''
    if request.method == 'POST':
        try:
            dados = request.form.to_dict()
            valores = [
                dados.get('tag_equipamento', ''),
                dados.get('matricula_saida', ''),
                dados.get('matricula_entrada', ''),
                dados.get('motivo', ''),
                dados.get('responsavel', '')
            ]

            service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="'DADOS_MOVIMENTACAO'!A:E",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [valores]}
            ).execute()

            mensagem = '✅ Movimentação registrada com sucesso!'

        except Exception as e:
            mensagem = f'❌ Erro ao registrar movimentação: {str(e)}'

    return render_template('Movimentacao.html', message=mensagem)

if __name__ == '__main__':
    app.run(debug=True)
