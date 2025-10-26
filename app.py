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
    combinations = []
    max_days_per_type = 4
    for sabados_trabajados in range(max_days_per_type + 1):
        domingos_trabajados = services_required - sabados_trabajados
        if 0 <= domingos_trabajados <= max_days_per_type:
            combinations.append((sabados_trabajados, domingos_trabajados))
    return combinations

def create_display_map(combinations):
    """
    Crea un diccionario para mapear tuplas numéricas a cadenas de texto legibles.
    """
    return {
        combo: f"{combo[0]} Sábado(s), {combo[1]} Domingo(s)"
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
employee_type_names = [ chr(i+65) for i in range(NUMERO_TIPO_EMPLEADOS) ]  # 'A', 'B', 'C', ...

for type_name in employee_type_names:
    st.sidebar.markdown(f"### Configuración del Tipo {type_name}")
    max_employees = st.sidebar.number_input(f"Nº Máximo de empleados del Tipo {type_name}", min_value=0, value=150, step=1, key=f"max_{type_name}")
    services_per_employee = st.sidebar.number_input(f"Nº de servicios de fin de semana que cubre el Tipo {type_name}", min_value=1, value=4, max_value=8, step=1, key=f"serv_{type_name}")
    
    possible_combos = generate_possible_combinations(services_per_employee)
    display_map = create_display_map(possible_combos)
    
    selected_display_options = st.sidebar.multiselect(
        f"Combinaciones de turnos permitidas para el Tipo {type_name}",
        options=list(display_map.values()),
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

    # N_vars: Número TOTAL de empleados de cada tipo (A, B, C...)
    N_vars = pulp.LpVariable.dicts("TotalEmpleados", employee_type_names, lowBound=0, cat='Integer')

    # --- CORRECCIÓN 1: Definir x_vars ---
    # x_vars: Número de empleados del Tipo 'T' asignados al Patrón 'P'
    # Esta es la variable principal que faltaba definir.
    x_vars = {}
    for type_name in employee_type_names:
        # Creamos un diccionario de variables para cada tipo de empleado,
        # donde cada clave es una tupla 'pattern' (ej: (4, 0))
        # Nota: Usamos las tuplas como índices para las variables.
        x_vars[type_name] = pulp.LpVariable.dicts(
            name=f"Empleados_{type_name}",
            indices=employee_types_data[type_name]["selected_patterns"],
            lowBound=0,
            cat='Integer'
        )
    # --- FIN DE LA CORRECCIÓN 1 ---

    # Objetivo: Minimizar el número total de empleados
    model += pulp.lpSum(N_vars), "Minimizar_Plantilla_Total"

    # Restricción de Sábados
    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern[0]  # pattern[0] son los Sábados
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"]
    ) >= TOTAL_DEMANDA_SABADO, "Cobertura_Demanda_Sabados"

    # --- CORRECCIÓN 2: Restricción de Domingos ---
    # Se corrige la iteración (no era [1]) y el acceso al patrón (debe ser pattern[1])
    model += pulp.lpSum(
        x_vars[type_name][pattern] * pattern[1]  # pattern[1] son los Domingos
        for type_name in employee_type_names
        for pattern in employee_types_data[type_name]["selected_patterns"] # Iterar sobre la lista completa
    ) >= TOTAL_DEMANDA_DOMINGO, "Cobertura_Demanda_Domingos"
    # --- FIN DE LA CORRECCIÓN 2 ---

    # Restricciones de vínculo y máximos
    for type_name in employee_type_names:
        # El total de empleados de un tipo (N_vars) es la suma de los empleados
        # asignados a cada patrón permitido para ese tipo (x_vars)
        model += pulp.lpSum(
            x_vars[type_name][pattern] for pattern in employee_types_data[type_name]["selected_patterns"]
        ) == N_vars[type_name], f"Vinculo_Plantilla_{type_name}"
        
        # Restricción del número máximo de empleados por tipo
        model += N_vars[type_name] <= employee_types_data[type_name]["max_employees"], f"Maximo_Empleados_{type_name}"

    # Resolver el modelo
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    # --- MOSTRAR RESULTADOS ---
    st.header("Resultados de la Optimización")
    status = pulp.LpStatus[model.status]
    st.write(f"**Estado de la Solución:** {status}")

    if status == 'Optimal':
        total_empleados = pulp.value(model.objective)
        st.success(f"**Número Mínimo de Empleados Necesarios:** {math.ceil(total_empleados)}")

        results_data = []
        total_sabados_cubiertos = 0
        total_domingos_cubiertos = 0

        for type_name in employee_type_names:
            for pattern in employee_types_data[type_name]["selected_patterns"]:
                # Obtener el valor de la variable de decisión
                num_empleados = x_vars[type_name][pattern].value()
                
                if num_empleados > 0:
                    
                    # --- CORRECCIÓN 3: Cálculo y visualización de resultados ---
                    # Calcular aportes multiplicando por el índice correcto de la tupla
                    sabados_aportados = num_empleados * pattern[0]
                    domingos_aportados = num_empleados * pattern[1]
                    total_sabados_cubiertos += sabados_aportados
                    total_domingos_cubiertos += domingos_aportados
                    
                    results_data.append({
                        "Tipo de Empleado": f"Tipo {type_name}",
                        # Mostrar la tupla 'pattern' directamente
                        "Patrón de Trabajo (Sáb, Dom)": f"{pattern}", 
                        "Nº Empleados Asignados": int(num_empleados),
                        "Turnos de Sábado Aportados": int(sabados_aportados),
                        "Turnos de Domingo Aportados": int(domingos_aportados)
                    })
                    # --- FIN DE LA CORRECCIÓN 3 ---
        
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
