import streamlit as st
import pandas as pd
import math

# Funções de Cálculo
def calcular_consumo_diario(equipamentos):
    total_consumo_wh = 0
    max_continua_w = 0
    max_pico_w = 0
    for eq in equipamentos:
        nominal = eq['potencia_nominal'] * eq['quantidade']  # Multiplica pela quantidade
        tempo = eq['tempo_uso']
        pico = nominal * eq['fator_pico']

        consumo = nominal * tempo
        total_consumo_wh += consumo
        max_continua_w += nominal
        max_pico_w = max(max_pico_w, pico)

    max_continua_w *= st.session_state.simultaneidade * st.session_state.margem
    max_pico_w *= st.session_state.margem
    total_consumo_wh /= 1000
    consumo_ajustado = total_consumo_wh / st.session_state.eficiencia

    return consumo_ajustado, max_continua_w / 1000, max_pico_w / 1000

def sugerir_inversores(df_inversores, continua_kw, pico_kw):
    sugestoes = []
    for _, row in df_inversores.iterrows():
        qtd_necessaria = max(1, math.ceil(continua_kw / row['P. NOMINAL']))
        if qtd_necessaria > row['QTD. MAX. INV.']:
            sugestoes.append(f"{row['MODELO']} (excede QTD. MAX. INV. de {row['QTD. MAX. INV.']}; necessário {qtd_necessaria})")
        else:
            sugestoes.append(f"{qtd_necessaria}x {row['MODELO']} (Nom: {row['P. NOMINAL']}kW, Pico: {row['P. PICO']}kW)")
    if not sugestoes:
        return "Nenhuma opção encontrada."
    return sugestoes

def calcular_baterias(df_baterias, consumo_ajustado_kwh, autonomia_dias):
    if df_baterias.empty:
        return ["A aba 'BATERIAS' está vazia. Adicione dados para sugestões."]
    energia_total_kwh = consumo_ajustado_kwh * autonomia_dias
    sugestoes = []
    for _, row in df_baterias.iterrows():
        dod = row['DoD'] / 100
        eff = row['EFICIENCIA'] / 100
        capacidade_necessaria_ah = (energia_total_kwh * 1000) / (st.session_state.tensao * dod * eff)

        serie_necessaria = math.ceil(st.session_state.tensao / 12)
        paralelo_necessario = math.ceil(capacidade_necessaria_ah / row['CAPACIDADE_AH'])

        if serie_necessaria > row['PILHA MAX'] or paralelo_necessario > row['PARALELO MAX']:
            sugestoes.append(f"{row['MODELO']} (excede limites: Série max {row['PILHA MAX']}, Paralelo max {row['PARALELO MAX']})")
        else:
            qtd_total = serie_necessaria * paralelo_necessario
            sugestoes.append(f"{qtd_total}x {row['MODELO']} ({serie_necessaria} em série x {paralelo_necessario} em paralelo, Cap: {row['CAPACIDADE_AH']}Ah)")
    if not sugestoes:
        return "Nenhuma opção encontrada."
    return sugestoes

# Interface Streamlit
st.title("Dimensionamento de Inversores e Baterias")

# Uploader para a planilha
uploaded_file = st.file_uploader("Carregue a planilha dados_energia.xlsx", type=["xlsx"])
if uploaded_file is not None:
    try:
        df_equip = pd.read_excel(uploaded_file, sheet_name="EQUIPAMENTOS")
        uploaded_file.seek(0)
        df_inversores = pd.read_excel(uploaded_file, sheet_name="INVERSORES")
        uploaded_file.seek(0)
        df_baterias = pd.read_excel(uploaded_file, sheet_name="BATERIAS")

        # Filtrar NaN em EQUIPAMENTOS
        df_equip = df_equip.dropna(subset=['MODELO', 'POTENCIA', 'FATOR PICO'])
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {str(e)}. Verifique as abas.")
        df_equip = df_inversores = df_baterias = pd.DataFrame()
else:
    st.warning("Carregue a planilha para continuar.")
    df_equip = df_inversores = df_baterias = pd.DataFrame()

# Configurações Gerais (defaults editáveis)
st.header("Configurações Gerais")
st.session_state.tensao = st.number_input("Tensão do Sistema (V)", value=48)
st.session_state.autonomia = st.number_input("Autonomia (dias)", value=2)
st.session_state.simultaneidade = st.number_input("Fator Simultaneidade", value=0.8)
st.session_state.margem = st.number_input("Margem de Segurança", value=1.2)
st.session_state.eficiencia = st.number_input("Eficiência do Sistema", value=0.85)

# Equipamentos (nova estrutura: modelo, quantidade, tempo)
st.header("Equipamentos")
if 'equipamentos' not in st.session_state:
    st.session_state.equipamentos = []

# Adicionar equipamentos dinamicamente
if st.button("Adicionar Equipamento"):
    st.session_state.equipamentos.append({'modelo': None, 'quantidade': 1, 'tempo_uso': 1.0})

# Exibir e editar equipamentos adicionados
for i, eq in enumerate(st.session_state.equipamentos):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        modelo = st.selectbox(f"Equip {i+1} Nome", options=df_equip['MODELO'].tolist() if not df_equip.empty else [], key=f"modelo_{i}", index=0)
    with col2:
        if modelo and not df_equip.empty:
            row = df_equip[df_equip['MODELO'] == modelo].iloc[0]
            pot = row['POTENCIA']
            fator = row['FATOR PICO']
            st.write(f"Pot (W): {pot}")
            st.write(f"Fator Pico: {fator}")
        else:
            pot = 0
            fator = 1.0
            st.write("Pot (W): 0")
            st.write("Fator Pico: 1.0")
    with col3:
        quantidade = st.number_input(f"Quantidade", min_value=1, value=1, key=f"qtd_{i}")
    with col4:
        tempo = st.number_input(f"Tempo (h/dia)", value=1.0, key=f"tempo_{i}")

    st.session_state.equipamentos[i] = {
        'potencia_nominal': pot,
        'fator_pico': fator,
        'quantidade': quantidade,
        'tempo_uso': tempo
    }

# Botões
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("Calcular Dimensionamento"):
        if uploaded_file is None:
            st.error("Carregue a planilha primeiro.")
        else:
            consumo_kwh, continua_kw, pico_kw = calcular_consumo_diario(st.session_state.equipamentos)

            st.header("Resultados")
            st.write(f"Consumo Diário Ajustado: {consumo_kwh:.2f} kWh")
            st.write(f"Potência Contínua Necessária: {continua_kw:.2f} kW")
            st.write(f"Potência Pico Necessária: {pico_kw:.2f} kW")

            st.subheader("Sugestões de Inversores")
            for sug in sugerir_inversores(df_inversores, continua_kw, pico_kw):
                st.write(sug)

            st.subheader("Sugestões de Baterias")
            for sug in calcular_baterias(df_baterias, consumo_kwh, st.session_state.autonomia):
                st.write(sug)
with col_btn2:
    if st.button("Resetar Equipamentos"):
        st.session_state.equipamentos = []
        st.rerun()
