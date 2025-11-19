import streamlit as st
import cmath
import math
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, Union, List, Tuple
import json # Para salvar/carregar
import graphviz # Importado para visualização do circuito

st.set_page_config(layout="wide", page_title="Analisador de Circuitos AC")

st.title("Analisador de Circuitos Elétricos AC Avançado")

st.markdown("""
Este aplicativo analisa circuitos AC: Série, Paralelo e Misto (Ramos Série em Paralelo).
Adicione componentes, defina ramos (para mistos) e visualize resultados detalhados.
**Novidades:** Salve/Carregue circuitos, Edite componentes, Varredura de Frequência!
---
""")

# --- Cache para funções de cálculo ---
@st.cache_data
def cached_calculate_component_impedance(comp_data_tuple: Tuple[Tuple[str, Any], ...], freq: float) -> Tuple[complex, str]:
    comp_data = dict(comp_data_tuple)
    impedance = complex(float('nan'), float('nan'))
    display_text = "Erro: Dados inválidos ou tipo desconhecido"
    value1 = comp_data.get("value1")
    value2 = comp_data.get("value2")
    impedance_str_in = comp_data.get("impedance_str", "")
    comp_type = comp_data.get("type")

    if not isinstance(freq, (int, float)) or freq <= 0:
        display_text = "Erro: Frequência deve ser um número > 0 Hz"
        return impedance, display_text

    if comp_type == "R":
        if isinstance(value1, (int, float)) and value1 >= 0:
            impedance = complex(value1, 0)
            display_text = f"{value1:.2f} Ω"
        else: display_text = "Erro: Valor R inválido (deve ser numérico >= 0)"
    elif comp_type == "L":
        if isinstance(value1, (int, float)) and value1 > 1e-12:
            XL = 2 * math.pi * freq * value1
            impedance = complex(0, XL)
            display_text = f"{value1 * 1e3:.3f} mH ($X_L = {XL:.2f} \\, \\Omega$)"
        else: display_text = "Erro: Valor L inválido (deve ser numérico > 0)"
    elif comp_type == "C":
        if isinstance(value1, (int, float)) and value1 > 1e-18:
            if (2 * math.pi * freq * value1) == 0:
                XC = float('inf')
            else:
                XC = 1 / (2 * math.pi * freq * value1)
            impedance = complex(0, -XC)
            if value1 >= 1e-6: display_text = f"{value1 * 1e6:.3f} µF ($X_C = {XC:.2f} \\, \\Omega$)"
            elif value1 >= 1e-9: display_text = f"{value1 * 1e9:.3f} nF ($X_C = {XC:.2f} \\, \\Omega$)"
            else: display_text = f"{value1 * 1e12:.3f} pF ($X_C = {XC:.2f} \\, \\Omega$)"
        else: display_text = "Erro: Valor C inválido (deve ser numérico > 0)"
    elif comp_type == "Z":
        parsed_z_successfully = False
        if impedance_str_in:
            try:
                cleaned_str = str(impedance_str_in).replace(" ", "").replace("Ω", "").replace("J","j")
                impedance = complex(cleaned_str)
                display_text = f"{impedance.real:.2f} {'+' if impedance.imag >= 0 else '-'} j{abs(impedance.imag):.2f} Ω"
                parsed_z_successfully = True
            except ValueError:
                if isinstance(value1, (int, float)) and isinstance(value2, (int, float)): pass
                else: display_text = f"Erro Z (str): '{impedance_str_in}' formato inválido"

        if not parsed_z_successfully and isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            try:
                impedance = cmath.rect(value1, math.radians(value2))
                display_text = f"{value1:.2f}∠{value2:.2f}°"
                parsed_z_successfully = True
            except Exception: display_text = f"Erro Z (polar): {value1}∠{value2}°"

        if not parsed_z_successfully:
            if display_text == "Erro: Dados inválidos ou tipo desconhecido":
                display_text = f"Erro Z: Dados insuficientes ('{impedance_str_in}')"
    return impedance, display_text

def calculate_component_impedance_and_display(comp_data: Dict[str, Any], freq: float) -> Tuple[complex, str]:
    keys_for_hashing = ['type', 'value1', 'value2', 'impedance_str']
    comp_data_for_hashing = {k: comp_data.get(k) for k in keys_for_hashing}
    comp_data_tuple: Tuple[Tuple[str, Any], ...] = tuple(sorted(comp_data_for_hashing.items()))
    return cached_calculate_component_impedance(comp_data_tuple, freq)

# --- FUNÇÃO DE CÁLCULO PRINCIPAL DO CIRCUITO ---
def solve_circuit_for_frequency(
    elements_config: Any,
    circuit_type_str: str,
    frequency_hz: float,
    voltage_mag_V: float,
    voltage_type_str: str
) -> Dict[str, Any]:

    results: Dict[str, Any] = {
        "calc_ok": False,
        "total_impedance_circuit": complex(float('nan')),
        "I_total_circuit": complex(float('nan')),
        "S_complex": complex(float('nan')),
        "power_factor_val": float('nan'),
        "power_factor_lead_lag": "N/A",
        "calculated_element_details_list": [],
        "processed_elements_data_for_phasors": [],
        "error_messages": []
    }

    if not frequency_hz > 0:
        results["error_messages"].append("Frequência deve ser > 0 Hz para cálculo.")
        return results

    if voltage_type_str == "Pico":
        V_source_phasor_mag = voltage_mag_V
    else: # RMS
        V_source_phasor_mag = voltage_mag_V
    
    V_source_complex = complex(V_source_phasor_mag, 0)

    processed_elements_for_phasors_list = []
    calculated_element_details_list_temp = []

    try:
        if circuit_type_str == "Misto (Ramos Série em Paralelo)":
            branch_equivalent_impedances = []
            if not elements_config or not any(elements_config):
                results["error_messages"].append("Misto: Nenhum ramo configurado para cálculo.")
                return results

            for i, branch_as_tuple_of_comp_items in enumerate(elements_config):
                branch_Z_series_sum = complex(0,0)
                branch_components_phasor_data = []
                if not branch_as_tuple_of_comp_items: continue 

                for comp_idx, comp_items_tuple in enumerate(branch_as_tuple_of_comp_items):
                    comp_dict = dict(comp_items_tuple) 
                    z_comp, disp_text = calculate_component_impedance_and_display(comp_dict, frequency_hz)
                    if cmath.isnan(z_comp.real) or cmath.isnan(z_comp.imag):
                        results["error_messages"].append(f"Erro em Ramo {i+1}, Comp {comp_idx+1} ({comp_dict.get('type')}): {disp_text}")
                        return results
                    branch_Z_series_sum += z_comp
                    branch_components_phasor_data.append({
                        'id': f"R{i+1}-{comp_dict.get('type','?').upper()}{comp_idx+1}",
                        'Z': z_comp,
                        'original_data': comp_dict,
                        'display_text': disp_text.split('($')[0].strip()
                    })
                branch_equivalent_impedances.append(branch_Z_series_sum)
                processed_elements_for_phasors_list.append({
                    'id': f"Ramo {i+1}",
                    'branch_Z': branch_Z_series_sum,
                    'components_in_branch': branch_components_phasor_data,
                    'original_branch_index': i
                })

            if not branch_equivalent_impedances: 
                results["total_impedance_circuit"] = complex(float('inf'))
            else:
                inv_Z_total_sum = complex(0,0)
                has_valid_branch = False
                for z_branch in branch_equivalent_impedances:
                    if abs(z_branch) < 1e-9: 
                        inv_Z_total_sum = complex(float('inf')) 
                        break
                    if not cmath.isinf(z_branch.real) and not cmath.isinf(z_branch.imag):
                        inv_Z_total_sum += (1 / z_branch)
                        has_valid_branch = True
                
                if cmath.isinf(inv_Z_total_sum.real) or cmath.isinf(inv_Z_total_sum.imag): 
                    results["total_impedance_circuit"] = complex(0,0)
                elif not has_valid_branch or abs(inv_Z_total_sum) < 1e-12: 
                    results["total_impedance_circuit"] = complex(float('inf'))
                else:
                    results["total_impedance_circuit"] = 1 / inv_Z_total_sum

        elif circuit_type_str == "Série":
            if not elements_config:
                results["error_messages"].append("Série: Nenhum componente para cálculo.")
                return results
            Z_total_series = complex(0,0)
            for i, comp_items_tuple in enumerate(elements_config):
                comp_dict = dict(comp_items_tuple)
                z_comp, disp_text = calculate_component_impedance_and_display(comp_dict, frequency_hz)
                if cmath.isnan(z_comp.real) or cmath.isnan(z_comp.imag):
                    results["error_messages"].append(f"Erro em Comp {i+1} ({comp_dict.get('type')}): {disp_text}")
                    return results
                Z_total_series += z_comp
                processed_elements_for_phasors_list.append({
                    'id': f"{comp_dict.get('type','?').upper()}{i+1}",
                    'Z_equiv': z_comp, 
                    'Z': z_comp,
                    'original_data': comp_dict,
                    'display_text': disp_text.split('($')[0].strip()
                })
            results["total_impedance_circuit"] = Z_total_series

        elif circuit_type_str == "Paralelo":
            if not elements_config:
                results["error_messages"].append("Paralelo: Nenhum componente para cálculo.")
                return results
            inv_Z_total_parallel_sum = complex(0,0)
            has_valid_comp = False
            is_shorted = False
            for i, comp_items_tuple in enumerate(elements_config):
                comp_dict = dict(comp_items_tuple)
                z_comp, disp_text = calculate_component_impedance_and_display(comp_dict, frequency_hz)
                if cmath.isnan(z_comp.real) or cmath.isnan(z_comp.imag):
                    results["error_messages"].append(f"Erro em Comp {i+1} ({comp_dict.get('type')}): {disp_text}")
                    return results
                
                processed_elements_for_phasors_list.append({
                    'id': f"{comp_dict.get('type','?').upper()}{i+1}",
                    'Z_equiv': z_comp, 
                    'Z': z_comp,
                    'original_data': comp_dict,
                    'display_text': disp_text.split('($')[0].strip()
                })

                if abs(z_comp) < 1e-9: 
                    is_shorted = True
                    break 
                if not cmath.isinf(z_comp.real) and not cmath.isinf(z_comp.imag):
                    inv_Z_total_parallel_sum += (1/z_comp)
                    has_valid_comp = True
            
            if is_shorted:
                results["total_impedance_circuit"] = complex(0,0)
            elif not has_valid_comp or abs(inv_Z_total_parallel_sum) < 1e-12 : 
                results["total_impedance_circuit"] = complex(float('inf'))
            else:
                results["total_impedance_circuit"] = 1 / inv_Z_total_parallel_sum
        else:
            results["error_messages"].append(f"Tipo de circuito desconhecido: {circuit_type_str}")
            return results

        Z_total = results["total_impedance_circuit"]

        if abs(Z_total) < 1e-9: 
            results["I_total_circuit"] = complex(V_source_complex.real / 1e-9, V_source_complex.imag / 1e-9) 
            if abs(V_source_complex) < 1e-9 : results["I_total_circuit"] = complex(0)
        elif cmath.isinf(Z_total.real) or cmath.isinf(Z_total.imag) or abs(Z_total) > 1e12: 
            results["I_total_circuit"] = complex(0, 0)
        else:
            results["I_total_circuit"] = V_source_complex / Z_total

        I_total = results["I_total_circuit"]

        if cmath.isnan(I_total.real) or cmath.isnan(I_total.imag) or cmath.isinf(I_total.real) or cmath.isinf(I_total.imag):
            results["S_complex"] = complex(float('nan'))
            results["power_factor_val"] = float('nan')
            results["power_factor_lead_lag"] = "Indeterminado"
        else:
            results["S_complex"] = V_source_complex * I_total.conjugate()
            P_real = results["S_complex"].real
            S_aparente = abs(results["S_complex"])
            
            if S_aparente < 1e-9:
                results["power_factor_val"] = 1.0 
                results["power_factor_lead_lag"] = "Unitário (S ≈ 0)"
            else:
                results["power_factor_val"] = P_real / S_aparente
            
            phase_diff_rad = cmath.phase(Z_total) 
            if abs(phase_diff_rad) < 1e-3: 
                results["power_factor_lead_lag"] = "Unitário"
            elif phase_diff_rad > 0: 
                results["power_factor_lead_lag"] = "Atrasado"
            else: 
                results["power_factor_lead_lag"] = "Adiantado"
        
        for proc_elem in processed_elements_for_phasors_list:
            z_val_str = f"{proc_elem['Z'].real:.2f}{proc_elem['Z'].imag:+.2f}j" if isinstance(proc_elem.get('Z'), complex) else "N/A"
            detail = f"{proc_elem['id']} ({proc_elem.get('display_text','N/A')}): Z = {z_val_str} Ω"
            if circuit_type_str == "Série":
                if abs(I_total)>1e-9 and isinstance(proc_elem['Z'], complex) and cmath.isfinite(proc_elem['Z']):
                    Vc = I_total * proc_elem['Z']
                    detail += f", V = {abs(Vc):.2f}∠{math.degrees(cmath.phase(Vc)):.1f}° V"
            elif circuit_type_str == "Paralelo":
                Vc_par = V_source_complex 
                Ic = complex(0)
                if isinstance(proc_elem['Z'], complex) and cmath.isfinite(proc_elem['Z']):
                    if abs(proc_elem['Z']) > 1e-9: Ic = Vc_par / proc_elem['Z']
                    elif abs(proc_elem['Z']) < 1e-9 and abs(Vc_par) > 1e-9: Ic = complex(float('inf')) 
                detail += f", I = {abs(Ic):.2f}∠{math.degrees(cmath.phase(Ic)):.1f}° A"
            elif circuit_type_str == "Misto (Ramos Série em Paralelo)":
                Z_branch = proc_elem['branch_Z']
                I_branch = complex(0)
                if isinstance(Z_branch, complex) and cmath.isfinite(Z_branch):
                    if abs(Z_branch) > 1e-9: I_branch = V_source_complex / Z_branch
                    elif abs(Z_branch) <1e-9 and abs(V_source_complex)>1e-9 : I_branch = complex(float('inf'))
                detail = f"{proc_elem['id']}: Z_eq_ramo = {Z_branch.real:.2f}{Z_branch.imag:+.2f}j Ω, I_ramo = {abs(I_branch):.2f}∠{math.degrees(cmath.phase(I_branch)):.1f}° A"
            calculated_element_details_list_temp.append(detail)

        results["calculated_element_details_list"] = calculated_element_details_list_temp
        results["processed_elements_data_for_phasors"] = processed_elements_for_phasors_list
        if not results["error_messages"]:
            results["calc_ok"] = True

    except Exception as e:
        results["error_messages"].append(f"Erro inesperado no cálculo: {str(e)}")
        results["calc_ok"] = False

    return results

def init_session_state():
    defaults = {
        'components': [], 'branches': [], 'active_branch_index': 0,
        'frequency': 60.0, 'voltage_source_mag': 127.0, 'voltage_type': "RMS",
        'circuit_type': "Série", 'editing_component_id': None,
        'sweep_results': None # <-- CORREÇÃO: Adicionado para guardar os resultados da varredura
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

    if st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)" and not st.session_state.branches:
        st.session_state.branches = [[]]
        st.session_state.active_branch_index = 0

init_session_state()

# CORREÇÃO: Função para limpar os resultados da varredura
def clear_sweep_results():
    st.session_state.sweep_results = None

def serialize_circuit_state():
    state_to_save = {
        'frequency': st.session_state.frequency,
        'voltage_source_mag': st.session_state.voltage_source_mag,
        'voltage_type': st.session_state.voltage_type,
        'circuit_type': st.session_state.circuit_type,
        'components': st.session_state.components,
        'branches': st.session_state.branches,
        'active_branch_index': st.session_state.active_branch_index,
    }
    return json.dumps(state_to_save, indent=2)

def load_circuit_state_from_json(json_string: str):
    try:
        loaded_state = json.loads(json_string)
        st.session_state.frequency = loaded_state.get('frequency', 60.0)
        st.session_state.voltage_source_mag = loaded_state.get('voltage_source_mag', 127.0)
        st.session_state.voltage_type = loaded_state.get('voltage_type', "RMS")
        st.session_state.circuit_type = loaded_state.get('circuit_type', "Série")
        st.session_state.components = loaded_state.get('components', [])
        st.session_state.branches = loaded_state.get('branches', [])
        st.session_state.active_branch_index = loaded_state.get('active_branch_index', 0)

        if st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)" and not st.session_state.branches:
            st.session_state.branches = [[]]
            st.session_state.active_branch_index = 0
        elif st.session_state.circuit_type != "Misto (Ramos Série em Paralelo)":
                st.session_state.branches = []
                st.session_state.active_branch_index = 0

        st.session_state.editing_component_id = None
        clear_sweep_results() # Limpa resultados antigos ao carregar novo circuito
        st.success("Circuito carregado com sucesso!")
        st.rerun()
    except json.JSONDecodeError: st.error("Erro: Arquivo JSON inválido.")
    except Exception as e: st.error(f"Erro ao carregar o circuito: {e}")

st.sidebar.header("1. Configuração da Fonte")
st.session_state.frequency = st.sidebar.number_input("Frequência (Hz)", min_value=0.01, value=st.session_state.frequency, format="%.2f", key="freq_input_v5", on_change=clear_sweep_results)
st.session_state.voltage_source_mag = st.sidebar.number_input("Tensão da Fonte (V)", min_value=0.1, value=st.session_state.voltage_source_mag, format="%.2f", key="volt_mag_input_v5", on_change=clear_sweep_results)
voltage_options_list = ["RMS", "Pico"]
current_volt_type_idx_val = voltage_options_list.index(st.session_state.voltage_type) if st.session_state.voltage_type in voltage_options_list else 0
st.session_state.voltage_type = st.sidebar.selectbox("Tipo de Tensão", voltage_options_list, index=current_volt_type_idx_val, key="volt_type_sb_v5", on_change=clear_sweep_results)

st.sidebar.header("2. Tipo de Circuito")
circuit_type_options_list = ["Série", "Paralelo", "Misto (Ramos Série em Paralelo)"]
current_circuit_type_idx_val = circuit_type_options_list.index(st.session_state.circuit_type) if st.session_state.circuit_type in circuit_type_options_list else 0
new_circuit_type_val = st.sidebar.radio(
    "Selecione o tipo de circuito:",
    circuit_type_options_list, index=current_circuit_type_idx_val, key="circuit_type_radio_v5"
)
if new_circuit_type_val != st.session_state.circuit_type:
    st.session_state.circuit_type = new_circuit_type_val
    clear_sweep_results() # Limpa resultados ao mudar o tipo de circuito
    if new_circuit_type_val == "Misto (Ramos Série em Paralelo)":
        if not st.session_state.branches:
            st.session_state.branches = [[]]
            st.session_state.active_branch_index = 0
    else:
        st.session_state.branches = []
        st.session_state.active_branch_index = 0
    st.session_state.components = []
    st.session_state.editing_component_id = None
    st.rerun()

st.sidebar.header("💾 Salvar/Carregar Circuito")
circuit_json_str_val = serialize_circuit_state()
st.sidebar.download_button(
    label="Salvar Circuito", data=circuit_json_str_val,
    file_name="config_circuito.json", mime="application/json", key="save_circuit_btn_v5"
)
uploaded_file_val = st.sidebar.file_uploader("Carregar Circuito (JSON)", type=["json"], key="load_circuit_uploader_v5")
if uploaded_file_val is not None:
    json_string_to_load_val = uploaded_file_val.getvalue().decode("utf-8")
    load_circuit_state_from_json(json_string_to_load_val)

def get_actual_comp_type_fn(selected_option_string_fn: str) -> Union[str, None]:
    if selected_option_string_fn == "Resistor (R)": return "R"
    if selected_option_string_fn == "Indutor (L)": return "L"
    if selected_option_string_fn == "Capacitor (C)": return "C"
    if selected_option_string_fn == "Impedância Conhecida (Z)": return "Z"
    return None

component_options_list_global = ["Resistor (R)", "Indutor (L)", "Capacitor (C)", "Impedância Conhecida (Z)"]

is_misto_circuit = st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)"
st.sidebar.header(f"3. Componentes ({st.session_state.circuit_type})")

def display_edit_form(comp_data_to_edit: Dict[str, Any], edit_key_prefix: str) -> Union[Dict[str, Any], None]:
    comp_type_to_edit = comp_data_to_edit.get("type", "R")
    type_options_map_inv_edit = {"R":"Resistor (R)", "L":"Indutor (L)", "C":"Capacitor (C)", "Z":"Impedância Conhecida (Z)"}
    default_type_str_edit = type_options_map_inv_edit.get(comp_type_to_edit, "Desconhecido")
    st.write(f"Editando: **{default_type_str_edit}** (Tipo não pode ser alterado aqui)")

    new_values_edit: Dict[str, Any] = {}

    if comp_type_to_edit == "R":
        r_val_edit = st.number_input("R (Ω)", min_value=0.0, value=float(comp_data_to_edit.get("value1", 10.0)), format="%.2f", key=f"{edit_key_prefix}_r_edit_val")
        new_values_edit["value1"] = r_val_edit
    elif comp_type_to_edit == "L":
        l_val_mH_edit = float(comp_data_to_edit.get("value1", 0.010) * 1000.0)
        l_val_new_mH_edit = st.number_input("L (mH)", min_value=0.000001, value=l_val_mH_edit, format="%.6f", key=f"{edit_key_prefix}_l_edit_val")
        new_values_edit["value1"] = l_val_new_mH_edit / 1000.0
    elif comp_type_to_edit == "C":
        default_c_uF_edit = float(comp_data_to_edit.get("value1", 10e-6) * 1e6)
        c_val_uF_edit_val = st.number_input(f"C (µF)", min_value=1e-9, value=default_c_uF_edit, format="%.3f", key=f"{edit_key_prefix}_c_val_edit_uF")
        new_values_edit["value1"] = c_val_uF_edit_val / 1e6
    elif comp_type_to_edit == "Z":
        initial_edit_mode_idx_z = 0
        v1_z_edit = comp_data_to_edit.get("value1")
        v2_z_edit = comp_data_to_edit.get("value2")
        impedance_str_z_edit = str(comp_data_to_edit.get("impedance_str",""))

        if (v1_z_edit is None or v2_z_edit is None) and "∠" not in impedance_str_z_edit:
                initial_edit_mode_idx_z = 1
        elif isinstance(v1_z_edit, (int, float)) and isinstance(v2_z_edit, (int, float)) and ("∠" in impedance_str_z_edit or not impedance_str_z_edit):
                initial_edit_mode_idx_z = 0

        edit_mode_z_val = st.radio("Editar Z como:", ["Polar", "Retangular"], index=initial_edit_mode_idx_z, key=f"{edit_key_prefix}_z_edit_mode", horizontal=True)
        if edit_mode_z_val == "Polar":
            default_mag_z, default_ang_z = 10.0, 0.0
            try: default_mag_z = float(v1_z_edit if v1_z_edit is not None else default_mag_z)
            except: pass
            try: default_ang_z = float(v2_z_edit if v2_z_edit is not None else default_ang_z)
            except: pass
            z_mag_edit_val = st.number_input("|Z| (Ω)", min_value=0.0, value=default_mag_z, format="%.2f", key=f"{edit_key_prefix}_z_mag_edit_polar")
            z_ang_edit_val = st.number_input("∠Z (°)", value=default_ang_z, format="%.2f", key=f"{edit_key_prefix}_z_ang_edit_polar")
            new_values_edit["value1"] = z_mag_edit_val
            new_values_edit["value2"] = z_ang_edit_val
            new_values_edit["impedance_str"] = f"{z_mag_edit_val:.2f}∠{z_ang_edit_val:.2f}°"
        else:
            default_rect_str_z = "10+0j"
            current_impedance_str_z = impedance_str_z_edit if impedance_str_z_edit and "∠" not in impedance_str_z_edit else default_rect_str_z
            if isinstance(v1_z_edit, (int, float)) and isinstance(v2_z_edit, (int, float)) and "∠" in impedance_str_z_edit:
                try:
                    rect_val_z = cmath.rect(v1_z_edit, math.radians(v2_z_edit))
                    current_impedance_str_z = f"{rect_val_z.real:.2f}{rect_val_z.imag:+.2f}j".replace("+-","-")
                except: pass
            z_str_edit_val = st.text_input("Z Retangular (ex: 10+5j, -20-10j, 5j, -8)", value=current_impedance_str_z, key=f"{edit_key_prefix}_z_str_edit_rect")
            new_values_edit["impedance_str"] = z_str_edit_val
            new_values_edit["value1"] = None
            new_values_edit["value2"] = None
    if st.form_submit_button("Salvar Alterações"): return new_values_edit
    return None

target_list_name_sidebar = "branches" if is_misto_circuit else "components"

if is_misto_circuit:
    st.sidebar.subheader("Gerenciar Ramos")
    if st.sidebar.button("Adicionar Novo Ramo Vazio", key="add_new_branch_btn_misto_ui_v5"):
        st.session_state.branches.append([])
        st.session_state.active_branch_index = len(st.session_state.branches) - 1
        st.session_state.editing_component_id = None
        clear_sweep_results()
        st.rerun()

    branch_names_sidebar = [f"Ramo {i+1}" for i in range(len(st.session_state.branches))]
    current_active_branch_idx_sidebar = st.session_state.active_branch_index
    if not st.session_state.branches: current_active_branch_idx_sidebar = 0
    elif current_active_branch_idx_sidebar >= len(st.session_state.branches):
        current_active_branch_idx_sidebar = max(0, len(st.session_state.branches) - 1)

    if branch_names_sidebar:
        new_idx_sidebar = st.sidebar.selectbox(
            "Editar Ramo:", options=range(len(st.session_state.branches)),
            format_func=lambda x_ui: branch_names_sidebar[x_ui],
            index=current_active_branch_idx_sidebar, key="select_active_branch_misto_ui_v5"
        )
        if new_idx_sidebar != st.session_state.active_branch_index:
            st.session_state.active_branch_index = new_idx_sidebar
            st.session_state.editing_component_id = None
            st.rerun()
    elif is_misto_circuit : st.sidebar.info("Nenhum ramo para editar.")

components_to_manage_sidebar: List[Dict[str, Any]]
branch_display_name_sidebar = ""
if is_misto_circuit:
    idx_to_access_sidebar = st.session_state.active_branch_index
    if st.session_state.branches and 0 <= idx_to_access_sidebar < len(st.session_state.branches):
        components_to_manage_sidebar = st.session_state.branches[idx_to_access_sidebar]
        branch_display_name_sidebar = f"Ramo {idx_to_access_sidebar + 1}"
    else: 
        components_to_manage_sidebar = []
        branch_display_name_sidebar = "Ramo (Inválido/Vazio)" if st.session_state.branches else "Nenhum Ramo"
        if is_misto_circuit and not st.session_state.branches:
                st.session_state.branches = [[]] 
                st.session_state.active_branch_index = 0
else:
    components_to_manage_sidebar = st.session_state.components
    branch_display_name_sidebar = st.session_state.circuit_type 

add_section_label_sidebar = f"Adicionar componente ao {branch_display_name_sidebar}" if is_misto_circuit and branch_display_name_sidebar and st.session_state.branches else "Adicionar novo componente:"
selected_comp_add_sidebar = st.sidebar.selectbox(add_section_label_sidebar, ["Selecione..."] + component_options_list_global, key=f"sb_add_comp_{target_list_name_sidebar}_v5")

if selected_comp_add_sidebar != "Selecione...":
    if is_misto_circuit and not st.session_state.branches:
        st.sidebar.warning("Adicione um ramo antes de adicionar componentes.")
    else:
        len_comps_sidebar = len(components_to_manage_sidebar)
        active_idx_val_sidebar = st.session_state.active_branch_index if is_misto_circuit else 0
        form_key_add_sidebar = f"add_form_{target_list_name_sidebar}_v5_{selected_comp_add_sidebar}_{active_idx_val_sidebar}_{len_comps_sidebar}"

        add_form_sidebar_obj = st.sidebar.form(key=form_key_add_sidebar)
        if add_form_sidebar_obj:
            with add_form_sidebar_obj:
                actual_type_add_sidebar = get_actual_comp_type_fn(selected_comp_add_sidebar)
                comp_to_add_sidebar: Dict[str, Any] = {"type": actual_type_add_sidebar}
                if actual_type_add_sidebar == "R": comp_to_add_sidebar["value1"] = st.number_input("R (Ω)", min_value=0.0, value=10.0, format="%.2f", key=f"r_add_{form_key_add_sidebar}")
                elif actual_type_add_sidebar == "L": comp_to_add_sidebar["value1"] = st.number_input("L (mH)", min_value=0.000001, value=10.0, format="%.6f", key=f"l_add_{form_key_add_sidebar}") / 1000.0
                elif actual_type_add_sidebar == "C":
                    c_unit_options_sidebar = {"µF": 1e-6, "nF": 1e-9, "pF": 1e-12, "F": 1.0}
                    c_unit_sidebar = st.selectbox("Unidade C", list(c_unit_options_sidebar.keys()), index=0, key=f"c_unit_add_{form_key_add_sidebar}")
                    c_val_in_sidebar = st.number_input(f"C ({c_unit_sidebar})", min_value=0.000001, value=10.0, format="%.6f", key=f"c_val_add_{form_key_add_sidebar}")
                    comp_to_add_sidebar["value1"] = c_val_in_sidebar * c_unit_options_sidebar[c_unit_sidebar]
                elif actual_type_add_sidebar == "Z":
                    z_input_type_add_sidebar = st.radio("Formato Z", ["Polar", "Retangular"], index=1, key=f"z_type_add_{form_key_add_sidebar}", horizontal=True)
                    if z_input_type_add_sidebar == "Polar":
                        z_mag_sidebar = st.number_input("|Z| (Ω)", min_value=0.0, value=10.0, format="%.2f", key=f"z_mag_add_{form_key_add_sidebar}")
                        z_angle_sidebar = st.number_input("∠Z (°)", value=0.0, format="%.2f", key=f"z_angle_add_{form_key_add_sidebar}")
                        comp_to_add_sidebar["value1"] = float(z_mag_sidebar)
                        comp_to_add_sidebar["value2"] = float(z_angle_sidebar)
                        comp_to_add_sidebar["impedance_str"] = f"{z_mag_sidebar:.2f}∠{z_angle_sidebar:.2f}°"
                    else:
                        z_str_sidebar = st.text_input("Z Retangular (ex: 10+5j, -20-10j, 5j, -8)", value="10+0j", key=f"z_str_add_{form_key_add_sidebar}")
                        comp_to_add_sidebar["impedance_str"] = z_str_sidebar
                        comp_to_add_sidebar["value1"] = None
                        comp_to_add_sidebar["value2"] = None

                if st.form_submit_button(f"Adicionar {selected_comp_add_sidebar}"):
                    if actual_type_add_sidebar:
                        if is_misto_circuit:
                            active_idx = st.session_state.active_branch_index
                            while active_idx >= len(st.session_state.branches):
                                st.session_state.branches.append([])
                            st.session_state.branches[active_idx].append(comp_to_add_sidebar)
                        else:
                            st.session_state.components.append(comp_to_add_sidebar)
                        st.session_state.editing_component_id = None
                        clear_sweep_results()
                        st.rerun()

main_col_components = st.columns(1)[0]
with main_col_components:
    if is_misto_circuit:
        st.subheader("Configuração dos Ramos e Componentes:")
        if st.session_state.branches:
            branch_names_main = [f"Ramo {i+1}" for i in range(len(st.session_state.branches))]
            for idx_b_disp_main, branch_list_disp_main in enumerate(st.session_state.branches):
                branch_label_disp_main = branch_names_main[idx_b_disp_main] if idx_b_disp_main < len(branch_names_main) else f"Ramo {idx_b_disp_main+1}"
                exp_label_disp_main = f"{branch_label_disp_main} ({'Ativo para adição na sidebar' if idx_b_disp_main == st.session_state.active_branch_index else 'Inativo para adição'}) - {'Vazio' if not branch_list_disp_main else f'{len(branch_list_disp_main)} comps.'}"
                is_expanded_disp_main = (idx_b_disp_main == st.session_state.active_branch_index) or bool(branch_list_disp_main)

                expander_branch_display_obj = st.expander(exp_label_disp_main, expanded=is_expanded_disp_main)
                if expander_branch_display_obj:
                    with expander_branch_display_obj:
                        if branch_list_disp_main:
                            for i_c_disp_main, c_data_disp_main in enumerate(branch_list_disp_main):
                                _, disp_inf_list_main = calculate_component_impedance_and_display(c_data_disp_main, st.session_state.frequency)
                                item_id_tuple_main = ("branches", idx_b_disp_main, i_c_disp_main)
                                cols_disp_main = st.columns([0.7, 0.15, 0.15])
                                cols_disp_main[0].markdown(f"&nbsp;&nbsp;▫ {c_data_disp_main.get('type','Inv')}{i_c_disp_main+1}: {disp_inf_list_main}")
                                if cols_disp_main[1].button("✏️", key=f"edit_m_v5_{idx_b_disp_main}_{i_c_disp_main}", help="Editar"):
                                    st.session_state.editing_component_id = item_id_tuple_main
                                    st.rerun()
                                if cols_disp_main[2].button("❌", key=f"del_m_v5_{idx_b_disp_main}_{i_c_disp_main}", help="Remover"):
                                    st.session_state.branches[idx_b_disp_main].pop(i_c_disp_main)
                                    if not st.session_state.branches[idx_b_disp_main] and len(st.session_state.branches) > 1: 
                                        st.session_state.branches.pop(idx_b_disp_main)
                                        st.session_state.active_branch_index = max(0, min(st.session_state.active_branch_index, len(st.session_state.branches)-1 if st.session_state.branches else 0))
                                    elif not st.session_state.branches: 
                                        st.session_state.branches = [[]] 
                                        st.session_state.active_branch_index = 0
                                    st.session_state.editing_component_id = None
                                    clear_sweep_results()
                                    st.rerun()

                                if st.session_state.editing_component_id == item_id_tuple_main:
                                    edit_form_key_main = f"edit_form_m_v5_{idx_b_disp_main}_{i_c_disp_main}"
                                    form_edit_misto_obj = st.form(key=edit_form_key_main)
                                    if form_edit_misto_obj:
                                        with form_edit_misto_obj:
                                            edited_vals_main = display_edit_form(c_data_disp_main, f"edit_m_inputs_v5_{idx_b_disp_main}_{i_c_disp_main}")
                                            if edited_vals_main: 
                                                for k_main, v_main in edited_vals_main.items():
                                                    if v_main is None and k_main in st.session_state.branches[idx_b_disp_main][i_c_disp_main]:
                                                        del st.session_state.branches[idx_b_disp_main][i_c_disp_main][k_main]
                                                    elif v_main is not None:
                                                        st.session_state.branches[idx_b_disp_main][i_c_disp_main][k_main] = v_main
                                                st.session_state.editing_component_id = None
                                                clear_sweep_results()
                                                st.rerun()
                        else:
                            st.write("&nbsp;&nbsp;&nbsp;&nbsp;_Este ramo está vazio._")

                        if st.button(f"Remover {branch_label_disp_main} Inteiro", key=f"del_branch_v5_{idx_b_disp_main}", help="Remover Ramo Inteiro"):
                            st.session_state.branches.pop(idx_b_disp_main)
                            if not st.session_state.branches: 
                                st.session_state.branches = [[]] 
                                st.session_state.active_branch_index = 0
                            else:
                                st.session_state.active_branch_index = max(0, min(st.session_state.active_branch_index, len(st.session_state.branches)-1))
                            st.session_state.editing_component_id = None
                            clear_sweep_results()
                            st.rerun()
        else:
            st.info("Modo Misto: Nenhum ramo configurado. Adicione ramos e componentes na barra lateral.")
            if not st.session_state.branches : 
                st.session_state.branches = [[]]
                st.session_state.active_branch_index = 0
    else: 
        st.subheader("Componentes Atuais no Circuito:")
        if st.session_state.components:
            for i_sp_main, comp_data_sp_main in enumerate(st.session_state.components):
                _, display_info_sp_main = calculate_component_impedance_and_display(comp_data_sp_main, st.session_state.frequency)
                item_id_tuple_sp_main = ("components", i_sp_main)
                cols_sp_main = st.columns([0.7, 0.15, 0.15])
                cols_sp_main[0].write(f"- {comp_data_sp_main.get('type','Inv')}{i_sp_main+1}: {display_info_sp_main}")
                if cols_sp_main[1].button("✏️", key=f"edit_sp_v5_{i_sp_main}", help="Editar"):
                    st.session_state.editing_component_id = item_id_tuple_sp_main
                    st.rerun()
                if cols_sp_main[2].button("❌", key=f"del_sp_v5_{i_sp_main}", help="Remover"):
                    st.session_state.components.pop(i_sp_main)
                    st.session_state.editing_component_id = None
                    clear_sweep_results()
                    st.rerun()

                if st.session_state.editing_component_id == item_id_tuple_sp_main:
                    expander_edit_sp_obj = st.expander(f"Editando {comp_data_sp_main.get('type','Inv')}{i_sp_main+1}", expanded=True)
                    if expander_edit_sp_obj:
                        with expander_edit_sp_obj:
                            form_edit_sp_obj = st.form(key=f"edit_form_sp_v5_{i_sp_main}")
                            if form_edit_sp_obj:
                                with form_edit_sp_obj:
                                    edited_vals_sp_main = display_edit_form(comp_data_sp_main, f"edit_sp_inputs_v5_{i_sp_main}")
                                    if edited_vals_sp_main:
                                        for k_sp_main, v_sp_main in edited_vals_sp_main.items():
                                            if v_sp_main is None and k_sp_main in st.session_state.components[i_sp_main]:
                                                del st.session_state.components[i_sp_main][k_sp_main]
                                            elif v_sp_main is not None:
                                                st.session_state.components[i_sp_main][k_sp_main] = v_sp_main
                                        st.session_state.editing_component_id = None
                                        clear_sweep_results()
                                        st.rerun()
        else:
            st.info("Nenhum componente. Adicione componentes na barra lateral.")

def generate_circuit_schematic(circuit_type_gv_fn, elements_gv_fn, current_freq_gv_fn, voltage_gv_fn, voltage_type_gv_fn):
    dot_gv = graphviz.Digraph(comment=f'Circuito {circuit_type_gv_fn}', format='svg')
    dot_gv.attr(rankdir='LR', splines='ortho', concentrate='false', nodesep='0.4', ranksep='0.6', fontname="Arial", fontsize="10")
    dot_gv.node_attr.update(shape='box', style='filled', height='0.45', fontname="Arial", fontsize='9')
    dot_gv.edge_attr.update(fontsize='8', fontname="Arial")

    source_node_name_gv_fn = "V_source_schematic_v5"
    dot_gv.node(source_node_name_gv_fn, f'Vs\n{voltage_gv_fn:.1f}V {voltage_type_gv_fn}\n{current_freq_gv_fn:.1f}Hz',
                shape='circle', style='filled', fillcolor='lightcoral', fontsize='9', fixedsize='true', width='0.7', height='0.7')

    if not elements_gv_fn or (isinstance(elements_gv_fn, list) and all(not el_gv for el_gv in elements_gv_fn)):
        empty_label_gv_fn = "Circuito Vazio"
        if circuit_type_gv_fn == "Misto (Ramos Série em Paralelo)" and isinstance(elements_gv_fn, list) and not any(elements_gv_fn):
            empty_label_gv_fn = "Misto: Adicione ramos e componentes"
        elif not elements_gv_fn : 
            empty_label_gv_fn = f"{circuit_type_gv_fn}: Adicione componentes"
        dot_gv.node("empty_circuit_node_schematic_v5", empty_label_gv_fn, shape='plaintext', fontsize='10')
        return dot_gv

    if circuit_type_gv_fn == "Série":
        prev_node_name_s_gv_fn = source_node_name_gv_fn
        s_return_point_gv_fn = "s_return_point_schematic_v5" 
        dot_gv.node(s_return_point_gv_fn, "", shape='point', width='0.01', height='0.01')

        for i_s_gv_fn, comp_s_data_gv_fn in enumerate(elements_gv_fn):
            _, comp_s_disp_gv_fn = calculate_component_impedance_and_display(comp_s_data_gv_fn, current_freq_gv_fn)
            label_s_gv_fn = f"{comp_s_data_gv_fn.get('type','?').upper()}{i_s_gv_fn+1}\n{comp_s_disp_gv_fn.split('($')[0].strip()}"
            node_name_s_gv_fn = f"s_comp_schematic_v5_{i_s_gv_fn}"
            dot_gv.node(node_name_s_gv_fn, label_s_gv_fn, fillcolor='lightskyblue')
            dot_gv.edge(prev_node_name_s_gv_fn, node_name_s_gv_fn)
            prev_node_name_s_gv_fn = node_name_s_gv_fn
        dot_gv.edge(prev_node_name_s_gv_fn, s_return_point_gv_fn) 
        dot_gv.edge(s_return_point_gv_fn, source_node_name_gv_fn, _attributes={'constraint':'false', 'dir':'back'}) 

    elif circuit_type_gv_fn == "Paralelo":
        node_p_start_gv_fn = "p_start_node_schematic_v5"
        node_p_end_gv_fn = "p_end_node_schematic_v5"
        dot_gv.node(node_p_start_gv_fn, "Nó A", shape='circle', style='filled', fillcolor='gray', fixedsize='true', width='0.2', height='0.2')
        dot_gv.node(node_p_end_gv_fn, "Nó B", shape='circle', style='filled', fillcolor='gray', fixedsize='true', width='0.2', height='0.2')
        dot_gv.edge(source_node_name_gv_fn, node_p_start_gv_fn)

        for i_p_gv_fn, comp_p_data_gv_fn in enumerate(elements_gv_fn):
            _, comp_p_disp_gv_fn = calculate_component_impedance_and_display(comp_p_data_gv_fn, current_freq_gv_fn)
            label_p_gv_fn = f"{comp_p_data_gv_fn.get('type','?').upper()}{i_p_gv_fn+1}\n{comp_p_disp_gv_fn.split('($')[0].strip()}"
            node_name_p_gv_fn = f"p_comp_schematic_v5_{i_p_gv_fn}"
            dot_gv.node(node_name_p_gv_fn, label_p_gv_fn, fillcolor='lightgreen')
            dot_gv.edge(node_p_start_gv_fn, node_name_p_gv_fn)
            dot_gv.edge(node_name_p_gv_fn, node_p_end_gv_fn)
        dot_gv.edge(node_p_end_gv_fn, source_node_name_gv_fn, _attributes={'dir':'back'})

    elif circuit_type_gv_fn == "Misto (Ramos Série em Paralelo)":
        common_start_node_gv_fn = "m_common_start_schematic_v5"
        common_end_node_gv_fn = "m_common_end_schematic_v5"
        dot_gv.node(common_start_node_gv_fn, "Nó A", shape='circle', style='filled', fillcolor='grey', fixedsize='true', width='0.2', height='0.2')
        dot_gv.node(common_end_node_gv_fn, "Nó B", shape='circle', style='filled', fillcolor='grey', fixedsize='true', width='0.2', height='0.2')
        dot_gv.edge(source_node_name_gv_fn, common_start_node_gv_fn)

        for branch_idx_gv_fn, branch_comp_list_gv_fn in enumerate(elements_gv_fn):
            if not branch_comp_list_gv_fn: continue

            cluster_name_gv_fn = f'cluster_branch_schematic_v5_{branch_idx_gv_fn}'
            
            subgraph_obj = dot_gv.subgraph(name=cluster_name_gv_fn)
            if subgraph_obj:
                with subgraph_obj as branch_subgraph_gv_fn:
                    branch_subgraph_gv_fn.attr(label=f'Ramo {branch_idx_gv_fn+1}', style='dashed', color='darkgrey', fontsize='9', rankdir='LR') 

                    first_node_in_branch_gv_fn = None
                    last_node_in_branch_gv_fn = None 
                    prev_comp_node_name_in_branch_gv_fn = None 

                    branch_entry_connector = f"branch_entry_{branch_idx_gv_fn}"
                    branch_exit_connector = f"branch_exit_{branch_idx_gv_fn}"

                    if len(branch_comp_list_gv_fn) > 1:
                        branch_subgraph_gv_fn.node(branch_entry_connector, "", shape='point', width='0.01')
                        branch_subgraph_gv_fn.node(branch_exit_connector, "", shape='point', width='0.01')
                        dot_gv.edge(common_start_node_gv_fn, branch_entry_connector, arrowhead='none') 
                        prev_comp_node_name_in_branch_gv_fn = branch_entry_connector
                    
                    for comp_idx_gv_fn, comp_m_data_gv_fn in enumerate(branch_comp_list_gv_fn):
                        current_comp_node_name_gv_fn = f"m_b_v5_{branch_idx_gv_fn}_c{comp_idx_gv_fn}_schematic"
                        _, comp_m_disp_gv_fn = calculate_component_impedance_and_display(comp_m_data_gv_fn, current_freq_gv_fn)
                        label_m_gv_fn = f"{comp_m_data_gv_fn.get('type','?').upper()}{branch_idx_gv_fn+1}.{comp_idx_gv_fn+1}\n{comp_m_disp_gv_fn.split('($')[0].strip()}"
                        branch_subgraph_gv_fn.node(current_comp_node_name_gv_fn, label_m_gv_fn, fillcolor='lightgoldenrodyellow')

                        if prev_comp_node_name_in_branch_gv_fn:
                            branch_subgraph_gv_fn.edge(prev_comp_node_name_in_branch_gv_fn, current_comp_node_name_gv_fn)
                        
                        if first_node_in_branch_gv_fn is None: 
                            first_node_in_branch_gv_fn = current_comp_node_name_gv_fn
                            if len(branch_comp_list_gv_fn) == 1: 
                                dot_gv.edge(common_start_node_gv_fn, first_node_in_branch_gv_fn)

                        prev_comp_node_name_in_branch_gv_fn = current_comp_node_name_gv_fn
                    
                    last_node_in_branch_gv_fn = prev_comp_node_name_in_branch_gv_fn 

                    if last_node_in_branch_gv_fn:
                        if len(branch_comp_list_gv_fn) > 1:
                            branch_subgraph_gv_fn.edge(last_node_in_branch_gv_fn, branch_exit_connector)
                            dot_gv.edge(branch_exit_connector, common_end_node_gv_fn, arrowhead='none') 
                        elif len(branch_comp_list_gv_fn) == 1 and first_node_in_branch_gv_fn: 
                            dot_gv.edge(first_node_in_branch_gv_fn, common_end_node_gv_fn)

        dot_gv.edge(common_end_node_gv_fn, source_node_name_gv_fn, _attributes={'dir':'back'}) 
    return dot_gv

st.markdown("---")
st.header("Esquema do Circuito")
current_elements_for_schematic_display_ui = []
if st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)":
    current_elements_for_schematic_display_ui = [b_ui for b_ui in st.session_state.get('branches', []) if b_ui] 
elif st.session_state.circuit_type in ["Série", "Paralelo"]:
    current_elements_for_schematic_display_ui = st.session_state.get('components', [])

has_elements_to_draw = False
if st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)":
    if any(branch for branch in current_elements_for_schematic_display_ui): 
        has_elements_to_draw = True
elif current_elements_for_schematic_display_ui: 
    has_elements_to_draw = True

if has_elements_to_draw:
    try:
        dot_obj_display_ui = generate_circuit_schematic(
            st.session_state.circuit_type,
            current_elements_for_schematic_display_ui,
            st.session_state.frequency,
            st.session_state.voltage_source_mag,
            st.session_state.voltage_type
        )
        st.graphviz_chart(dot_obj_display_ui)
    except graphviz.backend.execute.CalledProcessError as e_gv_exec_disp_ui:
        st.error(f"Erro ao renderizar o gráfico com Graphviz: {e_gv_exec_disp_ui}")
        st.info("Verifique se o software Graphviz (https://graphviz.org/download/) está instalado e se o diretório 'bin' dele está no PATH do sistema.")
    except Exception as e_gen_gv_disp_ui:
        st.error(f"Erro inesperado ao gerar o esquema: {e_gen_gv_disp_ui}")
else:
    st.info("Adicione componentes (ou configure ramos e adicione componentes a eles para o modo Misto) para visualizar o esquema do circuito.")

st.markdown("---")
main_calc_col_results_ui = st.columns(1)[0]
with main_calc_col_results_ui:
    st.header("4. Análise do Circuito e Resultados (Frequência Principal)")

    can_calculate_main = False
    elements_for_calc_tuple_final: Any = tuple() 

    if st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)":
        active_branches_final = [branch_list_final for branch_list_final in st.session_state.get('branches', []) if branch_list_final]
        if active_branches_final: 
            elements_for_calc_tuple_misto_temp_final = []
            for branch_data_final in active_branches_final:
                branch_comps_item_tuples = tuple(tuple(sorted(comp_final.items())) for comp_final in branch_data_final)
                elements_for_calc_tuple_misto_temp_final.append(branch_comps_item_tuples)
            elements_for_calc_tuple_final = tuple(elements_for_calc_tuple_misto_temp_final)
            can_calculate_main = True
    else: 
        components_final = st.session_state.get('components', [])
        if components_final:
            elements_for_calc_tuple_final = tuple(tuple(sorted(comp_final.items())) for comp_final in components_final)
            can_calculate_main = True

    if st.button("Calcular Circuito", type="primary", help="Clique para realizar os cálculos.", disabled=not can_calculate_main, key="btn_calc_circuit_main_v5"):
        clear_sweep_results() # Limpa resultados antigos da varredura ao recalcular o circuito
        if not can_calculate_main : 
                st.warning("Nenhum componente ou ramo válido para calcular.")
        elif st.session_state.frequency <=0:
                st.error("A frequência da fonte deve ser maior que zero para os cálculos principais.")
        else:
            analysis_results_final = solve_circuit_for_frequency(
                elements_for_calc_tuple_final,
                st.session_state.circuit_type,
                st.session_state.frequency,
                st.session_state.voltage_source_mag,
                st.session_state.voltage_type
            )

            if analysis_results_final["calc_ok"]:
                st.subheader("Detalhes Calculados dos Elementos do Circuito:")
                for detail_line_final in analysis_results_final["calculated_element_details_list"]: st.markdown(f"- {detail_line_final}")
                st.markdown("---"); st.subheader("Resultados Globais da Análise:")

                total_impedance_circuit_res = analysis_results_final["total_impedance_circuit"]
                I_total_circuit_res = analysis_results_final["I_total_circuit"]
                S_complex_res = analysis_results_final["S_complex"]
                fp_val_res = analysis_results_final["power_factor_val"]
                fp_lead_lag_res = analysis_results_final["power_factor_lead_lag"]

                Z_tot_mag_res, Z_tot_a_r_res = (float('inf'), 0)
                if isinstance(total_impedance_circuit_res, complex) and cmath.isfinite(total_impedance_circuit_res):
                    Z_tot_mag_res, Z_tot_a_r_res = cmath.polar(total_impedance_circuit_res)
                Z_tot_a_d_res = math.degrees(Z_tot_a_r_res)

                z_total_label_md_res = "**$Z_{total}$**"
                if isinstance(total_impedance_circuit_res, complex) and cmath.isfinite(total_impedance_circuit_res):
                    z_total_polar_latex_res = f"${Z_tot_mag_res:.2f} \\angle {Z_tot_a_d_res:.1f}° \\, \\Omega$"
                    z_total_rect_text_res = f"({total_impedance_circuit_res.real:.2f} {'+' if total_impedance_circuit_res.imag >= 0 else '-'} {abs(total_impedance_circuit_res.imag):.2f}j \\, \\Omega)"
                    st.markdown(f"{z_total_label_md_res}: {z_total_polar_latex_res} &nbsp; &nbsp; {z_total_rect_text_res}", unsafe_allow_html=True)
                else:
                    st.markdown(f"{z_total_label_md_res}: Infinita Ω (Circuito Aberto ou Indeterminado)")

                display_I_total_res = "0 A (Indeterminado)"
                if isinstance(I_total_circuit_res, complex) and cmath.isfinite(I_total_circuit_res):
                    if abs(total_impedance_circuit_res) < 1e-9 and abs(I_total_circuit_res) > 1e3: 
                        display_I_total_res = "Corrente Muito Alta (Curto-Circuito)"
                    elif abs(I_total_circuit_res) < 1e-9 : 
                        I_tot_mag_res_disp, I_tot_ang_rad_res_disp = cmath.polar(I_total_circuit_res)
                        I_tot_ang_deg_res_disp = math.degrees(I_tot_ang_rad_res_disp)
                        display_I_total_res = f"${I_tot_mag_res_disp:.2e} \\angle {I_tot_ang_deg_res_disp:.1f}° \\, A$ (Praticamente 0 A)"
                    else:
                        I_tot_mag_res_disp, I_tot_ang_rad_res_disp = cmath.polar(I_total_circuit_res)
                        I_tot_ang_deg_res_disp = math.degrees(I_tot_ang_rad_res_disp)
                        i_total_polar_latex_res = f"${I_tot_mag_res_disp:.2f} \\angle {I_tot_ang_deg_res_disp:.1f}° \\, A$"
                        i_total_rect_text_res = f"({I_total_circuit_res.real:.2f} {'+' if I_total_circuit_res.imag >= 0 else '-'} {abs(I_total_circuit_res.imag):.2f}j \\, A)"
                        display_I_total_res = f"{i_total_polar_latex_res} &nbsp; &nbsp; {i_total_rect_text_res}"
                elif cmath.isinf(total_impedance_circuit_res.real) or cmath.isinf(total_impedance_circuit_res.imag):
                        display_I_total_res = "0 A (Circuito Aberto)"

                st.markdown(f"**$I_{{total}}$:** {display_I_total_res}", unsafe_allow_html=True)

                if isinstance(S_complex_res, complex) and cmath.isfinite(S_complex_res):
                    st.markdown(f"**Potência Aparente (S):** ${abs(S_complex_res):.2f} \\, VA$")
                    st.markdown(f"**Potência Ativa (P):** ${S_complex_res.real:.2f} \\, W$")
                    st.markdown(f"**Potência Reativa (Q):** ${S_complex_res.imag:.2f} \\, VAR$")
                else:
                    st.markdown(f"**Potência Aparente (S):** N/A")
                    st.markdown(f"**Potência Ativa (P):** N/A")
                    st.markdown(f"**Potência Reativa (Q):** N/A")

                st.markdown(f"**Fator de Potência (FP):** ${fp_val_res:.3f}$ {fp_lead_lag_res if isinstance(fp_lead_lag_res, str) else 'N/A'}")

                phi_angle_display_res = f"${Z_tot_a_d_res:.1f}°$" if (isinstance(total_impedance_circuit_res, complex) and cmath.isfinite(total_impedance_circuit_res) and abs(total_impedance_circuit_res) > 1e-9) else "N/A"
                st.markdown(f"**Ângulo de defasagem ($\\phi$ Z_total):** {phi_angle_display_res}")

                st.markdown("---"); st.header("5. Representações Visuais (Frequência Principal)")
                can_plot_final_graphs_res_bool = analysis_results_final["calc_ok"] and \
                                                isinstance(total_impedance_circuit_res, complex) and cmath.isfinite(total_impedance_circuit_res) and \
                                                isinstance(I_total_circuit_res, complex) and cmath.isfinite(I_total_circuit_res) and \
                                                abs(total_impedance_circuit_res) > 1e-9 

                if can_plot_final_graphs_res_bool:
                    if st.session_state.voltage_type == "Pico":
                            source_V_complex_for_plot = complex(st.session_state.voltage_source_mag, 0)
                    else: 
                            source_V_complex_for_plot = complex(st.session_state.voltage_source_mag, 0) 

                    processed_data_phasors_res = analysis_results_final["processed_elements_data_for_phasors"]

                    st.subheader("5.1. Diagrama Fasorial"); fig_ph_final_res_plot, ax_ph_final_res_plot = plt.subplots(figsize=(8,6))
                    ax_ph_final_res_plot.axvline(0,c='grey',lw=0.5); ax_ph_final_res_plot.axhline(0,c='grey',lw=0.5); ax_ph_final_res_plot.grid(True,ls=':'); ax_ph_final_res_plot.set_aspect('equal')
                    ax_ph_final_res_plot.set_xlabel("Real"); ax_ph_final_res_plot.set_ylabel("Imaginário (j)"); ax_ph_final_res_plot.set_title(f"Fasores ({st.session_state.voltage_type}) - {st.session_state.circuit_type}")

                    mags_plot_final_list_res_plot = []
                    v_s_mag_plot_final_res_plot = abs(source_V_complex_for_plot); mags_plot_final_list_res_plot.append(v_s_mag_plot_final_res_plot)
                    ax_ph_final_res_plot.arrow(0,0,source_V_complex_for_plot.real, source_V_complex_for_plot.imag, head_width=v_s_mag_plot_final_res_plot*0.04, head_length=v_s_mag_plot_final_res_plot*0.08, fc='r',ec='r',lw=1.5,label=f"$V_S$: {v_s_mag_plot_final_res_plot:.2f}∠{math.degrees(cmath.phase(source_V_complex_for_plot)):.1f}°V")

                    i_t_mag_plot_final_res_plot = abs(I_total_circuit_res); mags_plot_final_list_res_plot.append(i_t_mag_plot_final_res_plot)
                    ax_ph_final_res_plot.arrow(0,0,I_total_circuit_res.real, I_total_circuit_res.imag, head_width=i_t_mag_plot_final_res_plot*0.04, head_length=i_t_mag_plot_final_res_plot*0.08, fc='b',ec='b',lw=1.5,label=f"$I_T$: {i_t_mag_plot_final_res_plot:.2f}∠{math.degrees(cmath.phase(I_total_circuit_res)):.1f}°A")

                    num_elements_for_cmap_res_plot = len(processed_data_phasors_res) if processed_data_phasors_res else 1
                    plot_clrs_cmap_final_res_plot = plt.get_cmap('viridis', num_elements_for_cmap_res_plot if num_elements_for_cmap_res_plot > 0 else 1)

                    if st.session_state.circuit_type == "Série":
                        v_cumulative_plot_final_res_plot = complex(0,0)
                        for k_final_res_s_plot, data_s_plot_res_plot in enumerate(processed_data_phasors_res):
                            Z_comp_plot_s_final_res_plot: complex = data_s_plot_res_plot['Z_equiv']
                            v_drop_k_plot_s_final_res_plot = I_total_circuit_res * Z_comp_plot_s_final_res_plot
                            v_drop_k_mag_plot_s_final_res_plot = abs(v_drop_k_plot_s_final_res_plot); mags_plot_final_list_res_plot.append(v_drop_k_mag_plot_s_final_res_plot)
                            ax_ph_final_res_plot.arrow(v_cumulative_plot_final_res_plot.real, v_cumulative_plot_final_res_plot.imag, v_drop_k_plot_s_final_res_plot.real, v_drop_k_plot_s_final_res_plot.imag,
                                                        head_width=v_drop_k_mag_plot_s_final_res_plot*0.03, head_length=v_drop_k_mag_plot_s_final_res_plot*0.06,
                                                        fc=plot_clrs_cmap_final_res_plot(k_final_res_s_plot % num_elements_for_cmap_res_plot), ec=plot_clrs_cmap_final_res_plot(k_final_res_s_plot % num_elements_for_cmap_res_plot), lw=1, ls='--',
                                                        label=f"$V_{{{data_s_plot_res_plot['id']}}}$ ({data_s_plot_res_plot['display_text']})")
                            v_cumulative_plot_final_res_plot += v_drop_k_plot_s_final_res_plot
                    elif st.session_state.circuit_type == "Paralelo":
                        for k_final_res_p_plot, data_p_plot_res_plot in enumerate(processed_data_phasors_res):
                            Z_comp_plot_p_final_res_plot: complex = data_p_plot_res_plot['Z_equiv']
                            i_branch_k_plot_p_final_res_plot = source_V_complex_for_plot / Z_comp_plot_p_final_res_plot if abs(Z_comp_plot_p_final_res_plot)>1e-9 else complex(float('inf')) 
                            if cmath.isinf(i_branch_k_plot_p_final_res_plot.real) : i_branch_k_plot_p_final_res_plot = complex(1e6) 

                            i_branch_k_mag_plot_p_final_res_plot = abs(i_branch_k_plot_p_final_res_plot); mags_plot_final_list_res_plot.append(i_branch_k_mag_plot_p_final_res_plot)
                            if i_branch_k_mag_plot_p_final_res_plot > 1e-9:
                                ax_ph_final_res_plot.arrow(0,0, i_branch_k_plot_p_final_res_plot.real, i_branch_k_plot_p_final_res_plot.imag,
                                                            head_width=i_branch_k_mag_plot_p_final_res_plot*0.03, head_length=i_branch_k_mag_plot_p_final_res_plot*0.06,
                                                            fc=plot_clrs_cmap_final_res_plot(k_final_res_p_plot % num_elements_for_cmap_res_plot), ec=plot_clrs_cmap_final_res_plot(k_final_res_p_plot % num_elements_for_cmap_res_plot), lw=1, ls=':',
                                                            label=f"$I_{{{data_p_plot_res_plot['id']}}}$ ({data_p_plot_res_plot['display_text']})")
                    elif st.session_state.circuit_type == "Misto (Ramos Série em Paralelo)":
                        for k_final_m_res_plot, branch_plot_item_m_final_res_plot in enumerate(processed_data_phasors_res):
                            Z_branch_plot_val_m_final_res_plot: complex = branch_plot_item_m_final_res_plot['branch_Z']
                            i_branch_plot_val_m_final_res_plot = source_V_complex_for_plot / Z_branch_plot_val_m_final_res_plot if abs(Z_branch_plot_val_m_final_res_plot)>1e-9 else complex(float('inf'))
                            if cmath.isinf(i_branch_plot_val_m_final_res_plot.real) : i_branch_plot_val_m_final_res_plot = complex(1e6) 

                            i_branch_plot_mag_val_m_final_res_plot = abs(i_branch_plot_val_m_final_res_plot); mags_plot_final_list_res_plot.append(i_branch_plot_mag_val_m_final_res_plot)
                            if i_branch_plot_mag_val_m_final_res_plot > 1e-9:
                                ax_ph_final_res_plot.arrow(0,0, i_branch_plot_val_m_final_res_plot.real, i_branch_plot_val_m_final_res_plot.imag,
                                                            head_width=i_branch_plot_mag_val_m_final_res_plot*0.03, head_length=i_branch_plot_mag_val_m_final_res_plot*0.06,
                                                            fc=plot_clrs_cmap_final_res_plot(k_final_m_res_plot % num_elements_for_cmap_res_plot), ec=plot_clrs_cmap_final_res_plot(k_final_m_res_plot % num_elements_for_cmap_res_plot), lw=1, ls=':',
                                                            label=f"$I_{{{branch_plot_item_m_final_res_plot['id']}}}$")

                    lim_p_final_res_plot_val = 0.0
                    valid_mags_for_lim_plot = [m_f_res_plot_val for m_f_res_plot_val in mags_plot_final_list_res_plot if math.isfinite(m_f_res_plot_val) and m_f_res_plot_val < 1e5] 
                    if valid_mags_for_lim_plot:
                        lim_p_final_res_plot_val = max(valid_mags_for_lim_plot) * 1.3 if valid_mags_for_lim_plot else 10.0
                    if lim_p_final_res_plot_val == 0 or not math.isfinite(lim_p_final_res_plot_val) or lim_p_final_res_plot_val > 1e5 : lim_p_final_res_plot_val = 10.0 if not valid_mags_for_lim_plot or max(valid_mags_for_lim_plot) > 1e5 else max(valid_mags_for_lim_plot)*1.3

                    ax_ph_final_res_plot.set_xlim((-lim_p_final_res_plot_val, lim_p_final_res_plot_val))
                    ax_ph_final_res_plot.set_ylim((-lim_p_final_res_plot_val, lim_p_final_res_plot_val))
                    ax_ph_final_res_plot.legend(loc='center left', bbox_to_anchor=(1.03,0.5), fontsize='small'); plt.tight_layout(rect=(0.0, 0.0, 0.82, 1.0))
                    st.pyplot(fig_ph_final_res_plot)

                    st.subheader("5.2. Formas de Onda"); fig_wv_final_res_plot, ax_wv_final_res_plot = plt.subplots(figsize=(10,5))
                    current_display_freq_plot = st.session_state.frequency if st.session_state.frequency > 0 else 60.0
                    t_wv_plot_final_res_plot = np.linspace(0,2/current_display_freq_plot,400)
                    
                    if st.session_state.voltage_type == "Pico":
                        v_pk_main_final_res_plot = st.session_state.voltage_source_mag
                    else: 
                        v_pk_main_final_res_plot = st.session_state.voltage_source_mag * math.sqrt(2)
                    
                    v_wv_main_final_res_plot = v_pk_main_final_res_plot * np.sin(2*np.pi*current_display_freq_plot*t_wv_plot_final_res_plot + cmath.phase(source_V_complex_for_plot))
                    ax_wv_final_res_plot.plot(t_wv_plot_final_res_plot*1000, v_wv_main_final_res_plot, 'r-', label=f"$V_S(t)$ (Pico: {v_pk_main_final_res_plot:.2f}V)")

                    if st.session_state.voltage_type == "Pico": 
                        i_pk_main_final_res_plot_corrected = abs(I_total_circuit_res)
                    else: 
                        i_pk_main_final_res_plot_corrected = abs(I_total_circuit_res) * math.sqrt(2)

                    i_wv_main_final_res_plot = i_pk_main_final_res_plot_corrected * np.sin(2*np.pi*current_display_freq_plot*t_wv_plot_final_res_plot + cmath.phase(I_total_circuit_res)) if isinstance(I_total_circuit_res, complex) and cmath.isfinite(I_total_circuit_res) else np.zeros_like(t_wv_plot_final_res_plot)
                    ax_wv_final_res_plot.plot(t_wv_plot_final_res_plot*1000, i_wv_main_final_res_plot, 'b-', label=f"$I_T(t)$ (Pico: {i_pk_main_final_res_plot_corrected:.2f}A)")
                    ax_wv_final_res_plot.set_xlabel("Tempo (ms)"); ax_wv_final_res_plot.set_ylabel("Amplitude (V,A)"); ax_wv_final_res_plot.grid(True); ax_wv_final_res_plot.legend(); ax_wv_final_res_plot.set_title("Tensão da Fonte e Corrente Total")
                    st.pyplot(fig_wv_final_res_plot)
                else:
                    st.info("Gráficos não gerados: cálculo principal incompleto, valores não finitos ou circuito em curto.")
            else:
                st.error("Cálculos não puderam ser concluídos. Verifique as entradas dos componentes e as mensagens de erro abaixo.")
                for err_msg_final in analysis_results_final.get("error_messages", []):
                    st.error(f"- {err_msg_final}")

    # ##################################################################
    # ## CORREÇÃO DA VARREDURA DE FREQUÊNCIA ##
    # ##################################################################
    st.markdown("---")
    st.subheader("6. Varredura de Frequência")
    
    expander_varredura_obj = st.expander("Configurar e Executar Varredura de Frequência")
    if expander_varredura_obj: 
        with expander_varredura_obj:
            sweep_col1_fs_v5, sweep_col2_fs_v5, sweep_col3_fs_v5 = st.columns(3)
            freq_start_fs_v5 = sweep_col1_fs_v5.number_input("Freq. Inicial (Hz)", min_value=0.01, value=1.0, format="%.2f", key="fs_start_v5")
            freq_stop_fs_v5 = sweep_col2_fs_v5.number_input("Freq. Final (Hz)", min_value=freq_start_fs_v5 if freq_start_fs_v5 > 0 else 0.01, value=1000.0, format="%.2f", key="fs_stop_v5")
            num_points_fs_v5 = sweep_col3_fs_v5.number_input("Nº de Pontos", min_value=2, max_value=1000, value=50, step=1, key="fs_points_v5")

            scale_options_fs_v5 = ["Linear", "Logarítmica"]
            scale_type_fs_v5 = st.radio("Escala de Frequência:", scale_options_fs_v5, index=0, horizontal=True, key="fs_scale_v5")
            
            # --- CORREÇÃO: Botões de controle da varredura ---
            btn_cols = st.columns(2)
            run_sweep = btn_cols[0].button("Executar Varredura", key="fs_run_btn_v5", disabled=not can_calculate_main, type="primary")
            clear_sweep = btn_cols[1].button("Limpar Gráficos", key="fs_clear_btn_v5")

            if clear_sweep:
                clear_sweep_results()
                st.rerun()

            # --- CORREÇÃO: Lógica de cálculo movida para o botão ---
            # O botão agora apenas calcula e salva os resultados no st.session_state
            if run_sweep:
                if freq_start_fs_v5 <=0 or freq_stop_fs_v5 <=0: st.error("Frequências de início e fim da varredura devem ser > 0.")
                elif freq_stop_fs_v5 < freq_start_fs_v5: st.error("Frequência final deve ser >= à inicial.")
                else:
                    freq_range_fs_v5: np.ndarray
                    if scale_type_fs_v5 == "Linear": freq_range_fs_v5 = np.linspace(freq_start_fs_v5, freq_stop_fs_v5, num_points_fs_v5)
                    else: freq_range_fs_v5 = np.logspace(np.log10(freq_start_fs_v5), np.log10(freq_stop_fs_v5), num_points_fs_v5)

                    if freq_range_fs_v5.size > 0:
                        sweep_Zmag_list_v5, sweep_Zphase_list_v5, sweep_Itmag_list_v5, sweep_Itphase_list_v5 = [], [], [], []
                        progress_bar_fs_v5 = st.progress(0, text="Calculando varredura...")
                        for i_fs_v5, freq_point_fs_v5 in enumerate(freq_range_fs_v5):
                            if freq_point_fs_v5 <= 0:
                                Z_tot_p_fs_v5, I_tot_p_fs_v5 = complex(float('nan')), complex(float('nan'))
                            else:
                                point_results_fs_v5 = solve_circuit_for_frequency( 
                                    elements_for_calc_tuple_final, 
                                    st.session_state.circuit_type, freq_point_fs_v5,
                                    st.session_state.voltage_source_mag, st.session_state.voltage_type
                                )
                                Z_tot_p_fs_v5 = point_results_fs_v5["total_impedance_circuit"]
                                I_tot_p_fs_v5 = point_results_fs_v5["I_total_circuit"]

                            sweep_Zmag_list_v5.append(abs(Z_tot_p_fs_v5) if isinstance(Z_tot_p_fs_v5, complex) and cmath.isfinite(Z_tot_p_fs_v5) else float('nan'))
                            sweep_Zphase_list_v5.append(math.degrees(cmath.phase(Z_tot_p_fs_v5)) if isinstance(Z_tot_p_fs_v5, complex) and cmath.isfinite(Z_tot_p_fs_v5) else float('nan'))
                            sweep_Itmag_list_v5.append(abs(I_tot_p_fs_v5) if isinstance(I_tot_p_fs_v5, complex) and cmath.isfinite(I_tot_p_fs_v5) else float('nan'))
                            sweep_Itphase_list_v5.append(math.degrees(cmath.phase(I_tot_p_fs_v5)) if isinstance(I_tot_p_fs_v5, complex) and cmath.isfinite(I_tot_p_fs_v5) else float('nan'))
                            progress_bar_fs_v5.progress((i_fs_v5 + 1) / num_points_fs_v5)
                        
                        progress_bar_fs_v5.empty()

                        # Salva tudo no st.session_state
                        st.session_state['sweep_results'] = {
                            "freq_range": freq_range_fs_v5,
                            "Zmag": sweep_Zmag_list_v5,
                            "Zphase": sweep_Zphase_list_v5,
                            "Itmag": sweep_Itmag_list_v5,
                            "Itphase": sweep_Itphase_list_v5,
                            "scale": scale_type_fs_v5
                        }
                        st.rerun()

        # --- CORREÇÃO: Lógica de exibição movida para fora do botão ---
        # Esta parte agora lê os dados do st.session_state e exibe os gráficos
        # em toda execução do script, garantindo que eles permaneçam na tela.
        if st.session_state.get('sweep_results'):
            results = st.session_state.sweep_results
            freq_range_fs_v5 = results["freq_range"]
            sweep_Zmag_list_v5 = results["Zmag"]
            sweep_Zphase_list_v5 = results["Zphase"]
            sweep_Itmag_list_v5 = results["Itmag"]
            sweep_Itphase_list_v5 = results["Itphase"]
            scale_type_fs_v5 = results["scale"]

            st.markdown("---")
            st.subheader("Resultados da Varredura")

            fig_sweep_Z_fs_v5, (ax_z_mag_fs_v5, ax_z_phase_fs_v5) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
            ax_z_mag_fs_v5.plot(freq_range_fs_v5, sweep_Zmag_list_v5, marker='.'); ax_z_mag_fs_v5.set_ylabel("|Z_total| (Ω)"); ax_z_mag_fs_v5.grid(True,ls=':')
            if scale_type_fs_v5 == "Logarítmica": ax_z_mag_fs_v5.set_xscale('log'); ax_z_mag_fs_v5.set_yscale('log')
            ax_z_phase_fs_v5.plot(freq_range_fs_v5, sweep_Zphase_list_v5, marker='.',c='r'); ax_z_phase_fs_v5.set_xlabel("Frequência (Hz)"); ax_z_phase_fs_v5.set_ylabel("Fase(Z_total) (°)"); ax_z_phase_fs_v5.grid(True,ls=':')
            if scale_type_fs_v5 == "Logarítmica": ax_z_phase_fs_v5.set_xscale('log')
            fig_sweep_Z_fs_v5.suptitle("Z_total vs Frequência"); plt.tight_layout(rect=(0,0,1,0.96)); st.pyplot(fig_sweep_Z_fs_v5)

            fig_sweep_I_fs_v5, (ax_i_mag_fs_v5, ax_i_phase_fs_v5) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
            ax_i_mag_fs_v5.plot(freq_range_fs_v5, sweep_Itmag_list_v5, marker='.'); ax_i_mag_fs_v5.set_ylabel("|I_total| (A)"); ax_i_mag_fs_v5.grid(True,ls=':')
            if scale_type_fs_v5 == "Logarítmica": ax_i_mag_fs_v5.set_xscale('log'); ax_i_mag_fs_v5.set_yscale('log')
            ax_i_phase_fs_v5.plot(freq_range_fs_v5, sweep_Itphase_list_v5, marker='.',c='g'); ax_i_phase_fs_v5.set_xlabel("Frequência (Hz)"); ax_i_phase_fs_v5.set_ylabel("Fase(I_total) (°)"); ax_i_phase_fs_v5.grid(True,ls=':')
            if scale_type_fs_v5 == "Logarítmica": ax_i_phase_fs_v5.set_xscale('log')
            fig_sweep_I_fs_v5.suptitle("I_total vs Frequência"); plt.tight_layout(rect=(0,0,1,0.96)); st.pyplot(fig_sweep_I_fs_v5)