import streamlit as st
import pulp
import pandas as pd
import math

# --- FUNCIONES AUXILIARES ---

def generate_possible_combinations(services_required):
    """
    Genera todas las combinaciones numéricas posibles de turnos de sábado y domingo
    para un número total de servicios dado.
    Devuelve una lista de tuplas (sabados, domingos).
    """
    # CORRECCIÓN: Se inicializa la lista vacía correctamente.
    combinations = []
    # El número máximo de sábados o domingos que se pueden trabajar es 4.
    max_days_per_type = 4
    for sabados_trabajados in range(max_days_per_type + 1):
        domingos_trabajados = services_required - sabados_trabajados
        # La combinación es válida si ambos valores están entre 0 y 4.
        if 0 <= domingos_trabajados <= max_days_per_type:
            combinations.append((sabados_trabajados, domingos_trabajados))
    return combinations

def create_display_map(combinations):
    """
    Crea un diccionario para mapear tuplas numéricas a cadenas de texto legibles.
    """
    # CORRECCIÓN: Se accede a los elementos de la tupla (combo y combo[1]) para un formato correcto.
    return {
        combo: f"{combo} Sábado(s), {combo[1]} Domingo(s)"
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

NUMERO_TIPO_EMPLEADOS = st.sidebar.selectbox("Número de tipos de empleados", (1, 2, 3, 4), index=1)

# --- RECOPILACIÓN DE DATOS POR TIPO DE EMPLEADO ---
employee_types_data = {}
# CORRECCIÓN: Se genera la lista de nombres de tipos de empleado (A, B, C...).
employee_type_names = [chr(65 + i) for i in range(NUMERO_TIPO_EMPLEADOS)]

for type_name in employee_type_names:
    st.sidebar.markdown(f"### Configuración del Tipo {type_name}")
    max_employees = st.sidebar.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
    services_per_employee = st.sidebar.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=4, max_value=8, step=1, key=f"serv_{type_name}")
    
    possible_combos = generate_possible_combinations(services_per_employee)
    display_map = create_display_map(possible_combos)
    
    selected_display_options = st.sidebar.multiselect(
        f"Combinaciones de turnos permitidas para el Tipo {type_name}",
        options=list(display_map.values()),
        default=list(display_map.values()),
        key=f"multi_{type_name}"
    )
    
    reverse_display_map = {v: k for k, v in display_map.items()}
    selected_combos_tuples = [reverse_display_map[option] for option in selected_display_options]
    
    employee_types_data[type_name] = {
        "max_employees": max_employees,
        "selected_patterns": selected_combos_tuples
    }

# --- BOTÓN DE CÁLCULO Y LÓGICA DE OPTIMIZACIÓN ---
if st.sidebar.button("Calcular Plantilla Óptima"):

    TOTAL_DEMANDA_SABADO = DEMANDA_SABADO * NUM_FINES_DE_SEMANA_MES
    TOTAL_DEMANDA_DOMINGO = DEMANDA_DOMINGO * NUM_FINES_DE_SEMANA_MES

    model = pulp.LpProblem("Minimizar_Plantilla_Fin_de_Semana", pulp.LpMinimize)

    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')
    x_vars = {}
    for type_name, data in employee_types_data.items():
        patterns = data["selected_patterns"]
        x_vars[type_name] = pulp.LpVariable.dicts(f"Asignacion_{type_name}", patterns, lowBound=0, cat='Integer')

    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern[1]
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"

    for type_name in employee_type_names:
        model += pulp.lpSum(
            x_vars[type_name][pattern] for pattern in employee_types_data[type_name]["selected_patterns"]
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"

    model.solve(pulp.PULP_CBC_CMD(msg=0))

    st.header("Resultados de la Optimización")
    status = pulp.LpStatus[model.status]
    st.write(f"**Estado de la Solución:** {status}")

    if status == 'Optimal':
        total_empleados = pulp.value(model.objective)
        st.success(f"**Número Mínimo de Empleados Necesarios:** {math.ceil(total_empleados)}")

        # CORRECCIÓN: Se inicializa la lista vacía correctamente.
        results_data = []
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            for pattern in employee_types_data[type_name]["selected_patterns"]:
                num_empleados = x_vars[type_name][pattern].value()
                if num_empleados > 0:
                    sabados_aportados = num_empleados * pattern
                    domingos_aportados = num_empleados * pattern[1]
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    results_data.append({
                        "Tipo de Empleado": f"Tipo {type_name}",
                        "Patrón de Trabajo (Sáb, Dom)": f"({pattern}, {pattern[1]})",
                        "Nº Empleados Asignados": int(num_empleados),
                        "Turnos de Sábado Aportados": int(sabados_aportados),
                        "Turnos de Domingo Aportados": int(domingos_aportados)
                    })
        
        if results_data:
            df_results = pd.DataFrame(results_data)
            st.dataframe(df_results, use_container_width=True)

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
