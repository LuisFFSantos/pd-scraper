import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os
import re
import pandas as pd
from io import BytesIO
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager
from shutil import which


# Configuração da página
st.set_page_config(
    page_title="Consulta Padrão",  # Título da aba do navegador
    page_icon="🔍"  # Ícone da aba (emoji ou caminho para arquivo)
)

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Executar em modo headless
    chrome_options.add_argument("--disable-gpu")  # Desativar GPU
    chrome_options.add_argument("--no-sandbox")  # Necessário para ambientes restritos
    chrome_options.add_argument("--disable-dev-shm-usage")  # Usar memória não compartilhada
    chrome_options.add_argument("--disable-software-rasterizer")  # Evitar problemas gráficos
    chrome_options.add_argument("--remote-debugging-port=9222")  # Porta de depuração
    chrome_options.add_argument("--log-level=3")  # Minimizar logs desnecessários

    # Defina o caminho do Google Chrome no Windows
    chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    chrome_options.binary_location = chrome_path

    # Verifique se o Chrome está disponível
    if not os.path.exists(chrome_path):
        st.error(f"O Chrome não foi encontrado no caminho: {chrome_path}")
        return None

    st.write(f"Caminho do Chrome detectado: {chrome_path}")

    try:
        chrome_service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=chrome_service, options=chrome_options)
    except Exception as e:
        st.error(f"Erro ao configurar o driver do Chrome: {e}")
        raise





def scrape_with_catalog(keyword):
    link = f'https://store.usp.org/product/{keyword}'
    driver = get_driver()
    try:
        driver.get(link)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'attr-value'))
        )

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        get = soup.find_all('div', attrs={"class": "usp-certificates"})
        lot_data = []

        for element in get:
            tbody = element.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    lot_number = row.find_all('td')[0].text.strip()
                    valid_date = row.find_all('td')[2].text.strip()
                    lot_number_cleaned = re.sub(r'\s*\(.*?\)', '', lot_number)

                    # Formatando a data para o padrão brasileiro e traduzindo "Current" para "Vigente"
                    if "Current" in valid_date:
                        valid_date = "Vigente"
                    else:
                        try:
                            valid_date = datetime.strptime(valid_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                        except ValueError:
                            try:
                                valid_date = datetime.strptime(valid_date, "%d-%b-%Y").strftime("%d/%m/%Y")
                            except ValueError:
                                valid_date = "Data Inválida"

                    # Criar link para download do certificado
                    certificate_url = f'https://static.usp.org/pdf/EN/referenceStandards/certificates/{keyword}-{lot_number_cleaned}.pdf'
                    lot_data.append((keyword, lot_number_cleaned, valid_date, certificate_url))

        return lot_data
    except Exception as e:
        st.error(f"Erro ao buscar dados para {keyword}: {e}")
        return []
    finally:
        driver.quit()

# Inicializar o estado da sessão
if 'results' not in st.session_state:
    st.session_state['results'] = []
if 'keywords' not in st.session_state:
    st.session_state['keywords'] = ""
if 'uploaded_file' not in st.session_state:
    st.session_state['uploaded_file'] = None
if 'reset_key' not in st.session_state:
    st.session_state['reset_key'] = 0
if 'history' not in st.session_state:
    st.session_state['history'] = []

# Interface principal
st.title("Consulta das validades dos Padrões USP")

# Sidebar para ajuda com componente expansível
with st.sidebar:
    st.header("Ajuda")
    with st.expander("Exibir Passo a Passo"):
        st.markdown("""
        **Como usar este sistema:**
        1. Insira os códigos dos produtos separados por vírgula na área de texto **ou** envie um arquivo Excel com os códigos.
        2. Clique no botão **Buscar** para iniciar a consulta.
        3. Os resultados serão exibidos em uma tabela com links para os certificados.
        4. Você pode baixar os resultados como um arquivo Excel.
        5. Clique em **Nova Consulta** para iniciar novamente.
        """)

# Input de códigos separados por vírgula
st.session_state['keywords'] = st.text_area("Insira os códigos dos produtos separados por vírgula:", value=st.session_state['keywords'])

# Upload de arquivo Excel
st.session_state['uploaded_file'] = st.file_uploader(
    "Ou envie um arquivo Excel com os códigos dos produtos:", type="xlsx", key=f"file_uploader_{st.session_state['reset_key']}"
)

# Definição inicial de keywords
keywords = []

if st.session_state['uploaded_file']:
    try:
        df = pd.read_excel(st.session_state['uploaded_file'])
        keywords.extend(df[df.columns[0]].astype(str).tolist())
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo Excel: {e}")

# Adiciona os códigos inseridos manualmente
if st.session_state['keywords']:
    keywords.extend(st.session_state['keywords'].split(','))

# Validação de entrada
keywords = [str(k).strip() for k in keywords if str(k).strip()]

if st.button("Buscar"):
    st.session_state.results = []

    with st.spinner("Buscando informações..."):
        for keyword in keywords:
            try:
                lot_data = scrape_with_catalog(keyword)
                st.session_state.results.extend(lot_data)
            except Exception as e:
                st.error(f"Erro ao buscar informações para {keyword}: {e}")

    # Salvar resultados no histórico
    if st.session_state.results:
        st.session_state['history'].append(st.session_state.results)

# Exibir resultados em tabela
if st.session_state.results:
    df_results = pd.DataFrame(st.session_state.results, columns=["Código do Produto", "Lote", "Validade", "Certificado"])
    st.write("### Resultados da Pesquisa")

    # Adicionar links clicáveis na coluna "Certificado"
    df_results["Certificado"] = df_results["Certificado"].apply(lambda x: f'<a href="{x}" target="_blank">Baixar Certificado</a>')

    # Renderizar tabela com links HTML
    st.write(df_results.to_html(escape=False, index=False), unsafe_allow_html=True)

    # Exportar resultados para Excel
    buffer = BytesIO()
    df_results.to_excel(buffer, index=False)
    buffer.seek(0)

    st.download_button(
        label="Baixar Resultados em Excel",
        data=buffer,
        file_name="resultados_certificados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Botão para limpar os resultados e redefinir os campos
    if st.button("Nova Consulta"):
        st.session_state['results'] = []
        st.session_state['keywords'] = ""
        st.session_state.pop('uploaded_file', None)
        st.session_state['reset_key'] += 1

# Exibir histórico de consultas
if st.session_state['history']:
    with st.expander("Histórico de Consultas"):
        for i, history in enumerate(st.session_state['history']):
            st.write(f"### Consulta {i + 1}")
            df_history = pd.DataFrame(history, columns=["Código do Produto", "Lote", "Validade", "Certificado"])
            df_history["Certificado"] = df_history["Certificado"].apply(lambda x: f'<a href="{x}" target="_blank">Baixar Certificado</a>')
            st.write(df_history.to_html(escape=False, index=False), unsafe_allow_html=True)
