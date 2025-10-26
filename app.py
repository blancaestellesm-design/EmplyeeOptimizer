import streamlit as st
import pulp
import pandas as pd
import math

# --- FUNCIONES AUXILIARES ---

def generate_possible_combinations(max_per_type):
    """
    Genera todas las combinaciones numéricas posibles de turnos de sábado y domingo.
    Devuelve una lista de tuplas (sabados, domingos).
    """
    combinations =
    for sabados_trabajados in range(max_per_type + 1):
        domingos_trabajados = max_per_type - sabados_trabajados
        combinations.append((sabados_trabajados, domingos_trabajados))
    return combinations

def create_display_map(combinations):
    """
    Crea un diccionario para mapear tuplas numéricas a cadenas de texto legibles.
    """
    return {
        combo: f"{combo} Sábado(s), {combo} Domingo(s)"
        for combo in combinations
    }

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(page_title="Optimizador de Plantilla", layout="wide")
st.title("Optimizador de Plantilla de Fin de Semana")
st.write("Esta herramienta calcula el número mínimo de empleados necesarios para cubrir la demanda de personal de los fines de semana, basándose en diferentes tipos de empleados y sus patrones de trabajo permitidos.")

# --- ENTRADAS DEL USUARIO EN LA BARRA LATERAL ---
st.sidebar.header("Parámetros de Entrada")
st.sidebar.write("Ajusta los valores y haz clic en 'Calcular' para ver el resultado.")

DEMANDA_SABADO = st.sidebar.number_input("Plazas necesarias por Sábado", min_value=0, value=116, step=1)
DEMANDA_DOMINGO = st.sidebar.number_input("Plazas necesarias por Domingo", min_value=0, value=81, step=1)
NUM_FINES_DE_SEMANA_MES = 4

st.sidebar.markdown("---")

NUMERO_TIPO_EMPLEADOS = st.sidebar.selectbox("Número de tipos de empleados", (1, 2, 3), index=1)

# --- RECOPILACIÓN DE DATOS POR TIPO DE EMPLEADO ---
employee_types_data = {}
employee_type_names =

for type_name in employee_type_names:
    st.sidebar.markdown(f"### Configuración del Tipo {type_name}")
    max_employees = st.sidebar.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=100, step=1, key=f"max_{type_name}")
    services_per_employee = st.sidebar.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=2, max_value=8, step=1, key=f"serv_{type_name}")
    
    # Generar combinaciones y mapa de visualización
    possible_combos = generate_possible_combinations(services_per_employee)
    display_map = create_display_map(possible_combos)
    
    # Obtener selecciones del usuario (cadenas de texto)
    selected_display_options = st.sidebar.multiselect(
        f"Combinaciones de turnos para el Tipo {type_name}",
        options=list(display_map.values()),
        default=list(display_map.values()), # Seleccionar todo por defecto
        key=f"multi_{type_name}"
    )
    
    # Convertir las selecciones de vuelta a tuplas numéricas para el modelo
    # Se crea un mapa inverso para facilitar la búsqueda
    reverse_display_map = {v: k for k, v in display_map.items()}
    selected_combos_tuples = [reverse_display_map[option] for option in selected_display_options]
    
    employee_types_data[type_name] = {
        "max_employees": max_employees,
        "selected_patterns": selected_combos_tuples
    }

# --- BOTÓN DE CÁLCULO Y LÓGICA DE OPTIMIZACIÓN ---
if st.sidebar.button("Calcular Plantilla Óptima"):

    # --- CÁLCULOS DE DEMANDA MENSUAL ---
    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * NUM_FINES_DE_SEMANA_MES
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * NUM_FINES_DE_SEMANA_MES

    # --- INICIALIZACIÓN DEL MODELO ---
    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana", pulp.LpMinimize)

    # --- VARIABLES DE DECISIÓN ---
    # N_i: Número total de empleados del tipo i
    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    # x_ij: Número de empleados del tipo i asignados al patrón j
    # Se utiliza un diccionario anidado para una estructura limpia: x_vars[tipo][patron]
    x_vars = {}
    for type_name, data in employee_types_data.items():
        # Los patrones son las tuplas (sabados, domingos)
        patterns = data["selected_patterns"]
        # El nombre de la variable se crea de forma sistemática para evitar conflictos
        var_keys = [f"{type_name}_{p}_{p}" for p in patterns]
        x_vars[type_name] = pulp.LpVariable.dicts("Asignacion", patterns, lowBound=0, cat='Integer')

    # --- FUNCIÓN OBJETIVO ---
    # Minimizar la suma de todos los empleados utilizados (la suma de las variables N_i)
    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # --- RESTRICCIONES ---
    # 1. Cobertura de la demanda de Sábados
    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern  # N_empleados * sabados_por_patron
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    # 2. Cobertura de la demanda de Domingos
    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern  # N_empleados * domingos_por_patron
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"

    # 3. y 4. Vínculo de variables y Límite máximo de empleados (por cada tipo)
    for type_name in employee_type_names:
        # 3. La suma de empleados en todos los patrones de un tipo debe ser igual al total de ese tipo (N_i)
        model += pulp.lpSum(
            x_vars[type_name][pattern] for pattern in employee_types_data[type_name]["selected_patterns"]
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"

        # 4. El total de empleados de un tipo (N_i) no puede exceder el máximo disponible
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"

    # --- RESOLUCIÓN DEL MODELO ---
    model.solve(pulp.PULP_CBC_CMD(msg=0)) # msg=0 para suprimir la salida del solver en la consola

    # --- PRESENTACIÓN DE RESULTADOS ---
    st.header("Resultados de la Optimización")
    
    status = pulp.LpStatus[model.status]
    st.write(f"**Estado de la Solución:** {status}")

    if status == 'Optimal':
        total_empleados = pulp.value(model.objective)
        st.success(f"**Número Mínimo de Empleados Necesarios:** {math.ceil(total_empleados)}")

        # Preparar datos para la tabla de resultados
        results_data =
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            for pattern in employee_types_data[type_name]["selected_patterns"]:
                num_empleados = x_vars[type_name][pattern].value()
                if num_empleados > 0:
                    sabados_aportados = num_empleados * pattern
                    domingos_aportados = num_empleados * pattern
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    results_data.append({
                        "Tipo de Empleado": f"Tipo {type_name}",
                        "Patrón de Trabajo (Sáb, Dom)": f"({pattern}, {pattern})",
                        "Nº Empleados Asignados": int(num_empleados),
                        "Turnos de Sábado Aportados": int(sabados_aportados),
                        "Turnos de Domingo Aportados": int(domingos_aportados)
                    })
        
        if results_data:
            df_results = pd.DataFrame(results_data)
            st.dataframe(df_results, use_container_width=True)

            # Resumen de cobertura
            st.subheader("Resumen de Cobertura de Demanda")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="Turnos de Sábado Cubiertos vs. Necesarios",
                    value=f"{int(total_sabados_cubiertos)}",
                    delta=f"{int(total_sabados_cubiertos - TOTAL_DEMANDA_SABADO)} (Excedente)"
                )
            with col2:
                st.metric(
                    label="Turnos de Domingo Cubiertos vs. Necesarios",
                    value=f"{int(total_domingos_cubiertos)}",
                    delta=f"{int(total_domingos_cubiertos - TOTAL_DEMANDA_DOMINGO)} (Excedente)"
                )
        else:
            st.info("La solución óptima no requiere asignar ningún empleado.")

    elif status == 'Infeasible':
        st.error(
            "**El problema no tiene solución (Infactible).** Esto significa que es imposible "
            "cumplir con la demanda especificada con las restricciones actuales de personal. "
            "**Sugerencias:**\n"
            "- Aumentar el 'Nº Máximo de empleados' para uno o más tipos.\n"
            "- Permitir patrones de trabajo más flexibles (más combinaciones de turnos).\n"
            "- Revisar si las cifras de demanda son correctas."
        )
    else:
        st.warning(f"**El modelo no encontró una solución óptima.** Estado: {status}. Revise los parámetros de entrada.")
