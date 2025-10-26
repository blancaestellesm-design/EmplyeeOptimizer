import streamlit as st
import pulp

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")
st.title("Optimizador de Plantilla de Fin de Semana")
st.write("Esta herramienta calcula el número mínimo de empleados necesarios para cubrir la demanda de personal de los fines de semana.")

# --- ENTRADAS DEL USUARIO EN LA BARRA LATERAL ---
st.sidebar.header("Parámetros de Entrada")
st.sidebar.write("Ajusta los valores y haz clic en 'Calcular' para ver el resultado.")

DEMANDA_SABADO = st.sidebar.number_input("Plazas necesarias los Sábados", min_value=0, value=116, step=1)
DEMANDA_DOMINGO = st.sidebar.number_input("Plazas necesarias los Domingos", min_value=0, value=81, step=1)
MAX_GRUPO_B = st.sidebar.number_input("Nº Máximo de empleados del Grupo B", min_value=0, value=150, step=1)
NUM_FINES_DE_SEMANA_MES = 4 # Se mantiene fijo a 4 semanas

# --- BOTÓN PARA EJECUTAR EL CÁLCULO ---
if st.sidebar.button("Calcular Plantilla Óptima"):

    # --- CÁLCULOS DE DEMANDA MENSUAL ---
    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * NUM_FINES_DE_SEMANA_MES
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * NUM_FINES_DE_SEMANA_MES

    # --- INICIALIZACIÓN DEL MODELO ---
    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana", pulp.LpMinimize)

    # --- VARIABLES DE DECISIÓN ---
    N_A = pulp.LpVariable("N_A", lowBound=0, cat='Integer')
    N_B1 = pulp.LpVariable("N_B1_Sat_Heavy", lowBound=0, cat='Integer')
    N_B2 = pulp.LpVariable("N_B2_Sun_Heavy", lowBound=0, cat='Integer')
    N_B3 = pulp.LpVariable("N_B3_Balanced", lowBound=0, cat='Integer')
    N_B_Total = pulp.LpVariable("N_B_Total", lowBound=0, cat='Integer')

    # --- FUNCIÓN OBJETIVO ---
    model += N_A + N_B_Total, "Total_Empleados"

    # --- RESTRICCIONES ---
    model += (1 * N_A) + (3 * N_B1) + (1 * N_B2) + (2 * N_B3) >= TOTAL_DEMANDA_SABADO, "Cobertura_Sabados"
    model += (1 * N_A) + (1 * N_B1) + (3 * N_B2) + (2 * N_B3) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Domingos"
    model += N_B_Total <= MAX_GRUPO_B, "Maximo_Grupo_B"
    model += N_B_Total == N_B1 + N_B2 + N_B3, "Definicion_Grupo_B"

    # --- RESOLUCIÓN DEL MODELO ---
    model.solve()

    # --- PRESENTACIÓN DE RESULTADOS ---
    st.header("Resultados de la Optimización")
    
    status = pulp.LpStatus[model.status]
    st.subheader(f"Estado de la Solución: {status}")

    if status == 'Optimal':
        n_a_opt = N_A.varValue
        n_b1_opt = N_B1.varValue
        n_b2_opt = N_B2.varValue
        n_b3_opt = N_B3.varValue
        n_b_total_opt = N_B_Total.varValue
        total_empleados_opt = n_a_opt + n_b_total_opt

        st.success(f"**Número Total Mínimo de Empleados Requerido: {int(total_empleados_opt)}**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Composición Óptima")
            st.metric(label="Empleados del Grupo A", value=int(n_a_opt))
            st.metric(label="Empleados Totales del Grupo B", value=int(n_b_total_opt))
            st.text(f"  - Subtipo B1 (Intensivo Sáb.): {int(n_b1_opt)}")
            st.text(f"  - Subtipo B2 (Intensivo Dom.): {int(n_b2_opt)}")
            st.text(f"  - Subtipo B3 (Equilibrado): {int(n_b3_opt)}")

        with col2:
            st.subheader("Análisis de Cobertura Mensual")
            cobertura_sabados = (1 * n_a_opt) + (3 * n_b1_opt) + (1 * n_b2_opt) + (2 * n_b3_opt)
            excedente_sabados = cobertura_sabados - TOTAL_DEMANDA_SABADO
            st.metric(label="Cobertura de Sábados", value=f"{int(cobertura_sabados)} turnos", delta=f"{int(excedente_sabados)} turnos de excedente")

            cobertura_domingos = (1 * n_a_opt) + (1 * n_b1_opt) + (3 * n_b2_opt) + (2 * n_b3_opt)
            excedente_domingos = cobertura_domingos - TOTAL_DEMANDA_DOMINGO
            st.metric(label="Cobertura de Domingos", value=f"{int(cobertura_domingos)} turnos", delta=f"{int(excedente_domingos)} turnos de excedente")
    else:
        st.error("No se encontró una solución óptima con los parámetros introducidos.")
