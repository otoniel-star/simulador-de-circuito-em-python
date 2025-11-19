import tkinter as tk
from tkinter import ttk, messagebox
import cmath # Para operações com números complexos
import math  # Para funções matemáticas como graus e radianos
import numpy as np # Para arrays e operações numéricas, especialmente para plotagem
import matplotlib.pyplot as plt # Para plotagem de gráficos

# --- Funções de Utilitário ---
def calcular_potencia_complexa(tensao_rms_fasor, corrente_rms_fasor):
    """Calcula potências ativa, reativa, aparente e fator de potência."""
    potencia_complexa = tensao_rms_fasor * corrente_rms_fasor.conjugate()
    P = potencia_complexa.real
    Q = potencia_complexa.imag
    S_aparente = abs(potencia_complexa)
    
    if S_aparente == 0:
        fp = 1.0
    else:
        fp = P / S_aparente
    
    return P, Q, S_aparente, fp, potencia_complexa

def complex_to_polar_str(z):
    """Converte um número complexo para o formato polar (magnitude < ângulo°)."""
    magnitude = abs(z)
    angulo_rad = cmath.phase(z)
    angulo_graus = math.degrees(angulo_rad)
    return f"{magnitude:.4f} < {angulo_graus:.2f}°"

def impedancia_serie(impedances):
    """Calcula a impedância equivalente de elementos em série."""
    return sum(impedances)

# --- Classes para Componentes e Grupos ---
class CircuitNode:
    """Representa um nó no circuito."""
    def __init__(self, name):
        self.name = name
        self.voltage = None # Fasor de tensão complexa relativo ao terra

class Component:
    """Classe base para componentes individuais (R, L, C, Z Conhecida)."""
    def __init__(self, value, name="Componente"):
        self.value = value
        self.name = name
        self.impedance = None # Impedância calculada em uma dada frequência
        self.voltage = None # Fasor de tensão sobre este componente
        self.current = None # Fasor de corrente através deste componente
        self.node_pos = None # Nó terminal positivo (para tensão)
        self.node_neg = None # Nó terminal negativo (para tensão)

    def calculate_impedance(self, freq_angular):
        raise NotImplementedError("Método calculate_impedance deve ser implementado por subclasses.")

    def get_details_string(self):
        return f"{self.name}={self.value}"

    def __repr__(self):
        return self.get_details_string()

class Resistor(Component):
    def __init__(self, value):
        super().__init__(value, name="R")
    
    def calculate_impedance(self, freq_angular):
        self.impedance = complex(self.value, 0)
        return self.impedance

    def get_details_string(self):
        return f"R={self.value}Ω"

class Inductor(Component):
    def __init__(self, value):
        super().__init__(value, name="L")
    
    def calculate_impedance(self, freq_angular):
        self.impedance = complex(0, freq_angular * self.value)
        return self.impedance

    def get_details_string(self):
        return f"L={self.value}H"

class Capacitor(Component):
    def __init__(self, value):
        super().__init__(value, name="C")
    
    def calculate_impedance(self, freq_angular):
        if self.value == 0:
            self.impedance = complex(0, -float('inf')) 
        else:
            self.impedance = complex(0, -1 / (freq_angular * self.value))
        return self.impedance

    def get_details_string(self):
        return f"C={self.value}F"

class ImpedanciaConhecida(Component):
    def __init__(self, magnitude, angle_deg):
        super().__init__(magnitude, name="Z")
        self.angle_deg = angle_deg
    
    def calculate_impedance(self, freq_angular):
        self.impedance = cmath.rect(self.value, math.radians(self.angle_deg))
        return self.impedance

    def get_details_string(self):
        return f"Z={self.value}Ω∠{self.angle_deg}°"

class CircuitGroup:
    """Representa um grupo de elementos em série ou paralelo."""
    def __init__(self, group_type, name="Grupo"):
        self.group_type = group_type # 'series' ou 'parallel'
        self.name = name
        self.elements = [] # Lista de Component ou CircuitGroup
        self.impedance = None # Impedância calculada de todo o grupo
        self.voltage = None # Fasor de tensão sobre este grupo
        self.current = None # Fasor de corrente através deste grupo

    def add_element(self, element):
        self.elements.append(element)
    
    def calculate_impedance(self, freq_angular):
        child_impedances = []
        for elem in self.elements:
            child_impedances.append(elem.calculate_impedance(freq_angular))
        
        if self.group_type == 'series':
            self.impedance = sum(child_impedances)
        elif self.group_type == 'parallel':
            self.impedance = self._calculate_parallel_impedance(child_impedances)
        return self.impedance

    def _calculate_parallel_impedance(self, impedances):
        # Auxiliar para cálculo paralelo para lidar com casos extremos
        if not impedances: return complex(0, -float('inf')) # Circuito aberto se vazio

        # Se houver qualquer curto-circuito (impedância ~0), o total é curto
        if any(abs(z) < 1e-9 for z in impedances):
            return complex(0, 0)

        valid_impedances = [z for z in impedances if abs(z) != float('inf')]
        if not valid_impedances: return complex(0, -float('inf')) # Todas as ramificações abertas

        try:
            sum_inverses = sum(1/z for z in valid_impedances)
            if abs(sum_inverses) < 1e-9: return complex(0, -float('inf')) # Evita divisão por zero se a soma dos inversos for muito pequena
            return 1 / sum_inverses
        except ZeroDivisionError:
            return complex(0, 0) # Equivalente a um curto-circuito

    def get_details_string(self):
        elem_details = ", ".join([e.get_details_string() for e in self.elements])
        return f"{self.group_type.capitalize()} Grupo: [{elem_details}]"

    def __repr__(self):
        return self.name

# --- Lógica da Interface Gráfica ---

class CalculadoraCircuitosPorGrupo:
    def __init__(self, master):
        self.master = master
        master.title("Calculadora de Circuitos CA (Completa)")
        # Removido master.geometry para permitir que o tamanho seja ajustado pelo conteúdo e scrollbars

        self.style = ttk.Style()
        self.style.configure("TLabel", font=("Arial", 10))
        self.style.configure("TButton", font=("Arial", 10, "bold"))
        self.style.configure("TEntry", font=("Arial", 10))
        self.style.configure("TCombobox", font=("Arial", 10))
        self.style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        self.style.configure("Treeview", font=("Arial", 10))

        # --- Configuração do Canvas e Scrollbar ---
        self.canvas = tk.Canvas(master, borderwidth=0)
        self.vertical_scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.canvas.yview)
        self.horizontal_scrollbar = ttk.Scrollbar(master, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set, xscrollcommand=self.horizontal_scrollbar.set)
        
        self.vertical_scrollbar.pack(side="right", fill="y")
        self.horizontal_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Frame que conterá todos os seus widgets e será rolado
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Configurar o redimensionamento do canvas e do frame
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind('<Enter>', self._bind_mouse_scroll)
        self.canvas.bind('<Leave>', self._unbind_mouse_scroll)

        # Variáveis de estado
        self.root_circuit_group = CircuitGroup('series', name="Circuito Principal")
        self.final_impedance = complex(0,0) 
        self.group_counter = 0 
        self.calculated_group_info = None
        self.circuit_history = []

        self.V_source_fasor = complex(0,0)
        self.I_total_fasor = complex(0,0)
        self.all_component_phasors = []

        self.create_widgets(self.scrollable_frame) # Passe o scrollable_frame como master para os widgets
        self.reset_circuit()

    def _bind_mouse_scroll(self, event):
        """Liga o scroll do mouse ao canvas quando o mouse entra na área do canvas."""
        self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mouse_wheel)

    def _unbind_mouse_scroll(self, event):
        """Desliga o scroll do mouse do canvas quando o mouse sai da área do canvas."""
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Shift-MouseWheel>")

    def _on_mouse_wheel(self, event):
        """Rola verticalmente com a roda do mouse."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_shift_mouse_wheel(self, event):
        """Rola horizontalmente com Shift + roda do mouse."""
        self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")

    def create_widgets(self, parent_frame):
        # --- Frame de Parâmetros Gerais ---
        general_params_frame = ttk.LabelFrame(parent_frame, text="Parâmetros da Fonte e Frequência", padding="10")
        general_params_frame.pack(padx=10, pady=5, fill="x", expand=False)

        ttk.Label(general_params_frame, text="Tensão da Fonte (V_rms) [V]:").grid(row=0, column=0, sticky="w", pady=2)
        self.v_source_entry = ttk.Entry(general_params_frame)
        self.v_source_entry.grid(row=0, column=1, sticky="ew", pady=2)
        self.v_source_entry.insert(0, "120")

        ttk.Label(general_params_frame, text="Frequência Base (f) [Hz]:").grid(row=1, column=0, sticky="w", pady=2)
        self.f_entry = ttk.Entry(general_params_frame)
        self.f_entry.grid(row=1, column=1, sticky="ew", pady=2)
        self.f_entry.insert(0, "60")
        
        # --- Frame para Definir Grupos ---
        define_group_frame = ttk.LabelFrame(parent_frame, text="Definir Novo Grupo", padding="10")
        define_group_frame.pack(padx=10, pady=5, fill="x", expand=False)

        ttk.Label(define_group_frame, text="Tipo de Grupo:").grid(row=0, column=0, sticky="w", pady=2)
        self.group_type_var = tk.StringVar(parent_frame) # Variável deve ser do master principal
        self.group_type_combo = ttk.Combobox(define_group_frame, textvariable=self.group_type_var,
                                              values=["R", "L", "C", "RL (Série)", "RC (Série)", "RLC (Série)", "Z Conhecida"])
        self.group_type_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.group_type_combo.set("R")
        self.group_type_combo.bind("<<ComboboxSelected>>", self.on_group_type_select)

        # Campos de entrada de valores para R, L, C, Z, Ângulo
        self.labels_entries = {}
        fields = [
            ("Resistência (R) [Ω]:", "r_val"),
            ("Indutância (L) [H]:", "l_val"),
            ("Capacitância (C) [F]:", "c_val"),
            ("Magnitude Z (Ω):", "z_mag_val"),
            ("Ângulo Z (graus):", "z_angle_val")
        ]
        
        for i, (text, var_name) in enumerate(fields):
            label = ttk.Label(define_group_frame, text=text)
            label.grid(row=i+1, column=0, sticky="w", pady=2)
            entry = ttk.Entry(define_group_frame)
            entry.grid(row=i+1, column=1, sticky="ew", pady=2)
            self.labels_entries[var_name] = (label, entry)
        
        self.define_group_button = ttk.Button(define_group_frame, text="Calcular Impedância do Grupo", command=self.calculate_group_impedance)
        self.define_group_button.grid(row=len(fields)+1, column=0, columnspan=2, pady=5, sticky="ew")

        # --- Frame para Adicionar Grupo Calculado ao Circuito Final ---
        add_to_final_frame = ttk.LabelFrame(parent_frame, text="Adicionar Grupo Calculado ao Circuito Final", padding="10")
        add_to_final_frame.pack(padx=10, pady=5, fill="x", expand=False)

        ttk.Button(add_to_final_frame, text="Adicionar em Série", command=lambda: self.add_group_to_final_circuit('series')).pack(side=tk.LEFT, expand=True, padx=2)
        ttk.Button(add_to_final_frame, text="Adicionar em Paralelo", command=lambda: self.add_group_to_final_circuit('parallel')).pack(side=tk.LEFT, expand=True, padx=2)

        # --- Histórico do Circuito Final ---
        history_frame = ttk.LabelFrame(parent_frame, text="Histórico do Circuito Final", padding="10")
        history_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.history_tree = ttk.Treeview(history_frame, columns=("Group", "Connection", "Total Z", "Details"), show="headings")
        self.history_tree.heading("Group", text="Grupo")
        self.history_tree.heading("Connection", text="Conexão")
        self.history_tree.heading("Total Z", text="Z Total Acumulada")
        self.history_tree.heading("Details", text="Detalhes do Grupo")
        self.history_tree.column("Group", width=80, stretch=tk.NO)
        self.history_tree.column("Connection", width=100, stretch=tk.NO)
        self.history_tree.column("Total Z", width=180, stretch=tk.NO)
        self.history_tree.column("Details", width=200, stretch=tk.YES)
        self.history_tree.pack(fill="both", expand=True)
        
        # --- Visualização da Impedância Final do Circuito ---
        final_impedance_frame = ttk.LabelFrame(parent_frame, text="Impedância Total do Circuito", padding="10")
        final_impedance_frame.pack(padx=10, pady=5, fill="x", expand=False)
        self.final_impedance_label = ttk.Label(final_impedance_frame, text="Z_total: ")
        self.final_impedance_label.pack(fill="x")
        
        # --- Botões de Plotagem e Reset ---
        plot_buttons_frame = ttk.Frame(parent_frame)
        plot_buttons_frame.pack(pady=5)

        plot_bode_button = ttk.Button(plot_buttons_frame, text="Plotar Resposta em Frequência (Magnitude)", command=self.plot_frequency_response)
        plot_bode_button.pack(side=tk.LEFT, padx=5)

        plot_phasor_button = ttk.Button(plot_buttons_frame, text="Plotar Diagrama Fasorial (Todos Fasores)", command=self.plot_all_phasors_diagram)
        plot_phasor_button.pack(side=tk.LEFT, padx=5)

        reset_button = ttk.Button(parent_frame, text="Resetar Circuito", command=self.reset_circuit)
        reset_button.pack(pady=10)

        # --- Frame de Resultados Finais ---
        results_frame = ttk.LabelFrame(parent_frame, text="Resultados Finais do Circuito na Frequência Base", padding="10")
        results_frame.pack(padx=10, pady=5, fill="x", expand=False)

        self.result_labels = {}
        result_texts = [
            "Corrente Total (I_total):",
            "Potência Ativa (P):",
            "Potência Reativa (Q):",
            "Potência Aparente (S):",
            "Fator de Potência (FP):"
        ]

        row_num = 0
        for text in result_texts:
            ttk.Label(results_frame, text=text).grid(row=row_num, column=0, sticky="w", pady=2)
            value_label = ttk.Label(results_frame, text="")
            value_label.grid(row=row_num, column=1, sticky="w", pady=2)
            self.result_labels[text] = value_label
            row_num += 1

        self.on_group_type_select() 

    def reset_circuit(self):
        self.root_circuit_group = CircuitGroup('series', name="Circuito Principal")
        self.final_impedance = complex(0,0)
        self.group_counter = 0
        self.calculated_group_info = None
        self.circuit_history = []
        self.all_component_phasors = []
        self.V_source_fasor = complex(0,0)
        self.I_total_fasor = complex(0,0)

        self.update_history_display() 
        self.update_final_impedance_display()
        self.clear_results()
        self.group_type_combo.set("R") 
        self.on_group_type_select() 

    def clear_results(self):
        for label_text in self.result_labels:
            self.result_labels[label_text].config(text="")

    def get_common_params(self):
        try:
            V_source_rms = float(self.v_source_entry.get())
            freq_hz = float(self.f_entry.get())
            if freq_hz <= 0:
                raise ValueError("A frequência deve ser maior que zero.")
            freq_angular = 2 * math.pi * freq_hz
            return V_source_rms, freq_hz, freq_angular
        except ValueError as e:
            messagebox.showerror("Erro de Entrada", f"Verifique os valores de tensão ou frequência.\nErro: {e}")
            return None, None, None

    def on_group_type_select(self, event=None):
        selected_type = self.group_type_var.get()
        
        for label_widget, entry_widget in self.labels_entries.values():
            entry_widget.config(state=tk.DISABLED)
            entry_widget.delete(0, tk.END) 
        
        if selected_type == "R":
            self.labels_entries["r_val"][1].config(state=tk.NORMAL)
        elif selected_type == "L":
            self.labels_entries["l_val"][1].config(state=tk.NORMAL)
        elif selected_type == "C":
            self.labels_entries["c_val"][1].config(state=tk.NORMAL)
        elif selected_type in ["RL (Série)", "RC (Série)", "RLC (Série)"]:
            self.labels_entries["r_val"][1].config(state=tk.NORMAL)
            if "L" in selected_type:
                self.labels_entries["l_val"][1].config(state=tk.NORMAL)
            if "C" in selected_type:
                self.labels_entries["c_val"][1].config(state=tk.NORMAL)
        elif selected_type == "Z Conhecida":
            self.labels_entries["z_mag_val"][1].config(state=tk.NORMAL)
            self.labels_entries["z_angle_val"][1].config(state=tk.NORMAL)

    def calculate_group_impedance(self):
        V_source_rms, freq_hz, freq_angular = self.get_common_params()
        if V_source_rms is None: return

        selected_type = self.group_type_var.get()
        group_impedance = complex(0,0)
        group_details_str = "" 
        group_elements = []

        try:
            R = float(self.labels_entries["r_val"][1].get() or 0)
            L = float(self.labels_entries["l_val"][1].get() or 0)
            C = float(self.labels_entries["c_val"][1].get() or 0)
            Z_mag = float(self.labels_entries["z_mag_val"][1].get() or 0)
            Z_angle = float(self.labels_entries["z_angle_val"][1].get() or 0)

            if (selected_type in ["R", "RL (Série)", "RC (Série)", "RLC (Série)"] and R < 0) or \
               (selected_type in ["L", "RL (Série)", "RLC (Série)"] and L < 0) or \
               (selected_type in ["C", "RC (Série)", "RLC (Série)"] and C < 0):
                raise ValueError("Valores de R, L, C não podem ser negativos.")
            if selected_type == "Z Conhecida" and Z_mag < 0:
                raise ValueError("Magnitude da Impedância Conhecida não pode ser negativa.")

            if selected_type == "R":
                comp_R = Resistor(R)
                group_impedance = comp_R.calculate_impedance(freq_angular)
                group_details_str = comp_R.get_details_string()
                group_elements = [comp_R]
            elif selected_type == "L":
                comp_L = Inductor(L)
                group_impedance = comp_L.calculate_impedance(freq_angular)
                group_details_str = comp_L.get_details_string()
                group_elements = [comp_L]
            elif selected_type == "C":
                comp_C = Capacitor(C)
                group_impedance = comp_C.calculate_impedance(freq_angular)
                group_details_str = comp_C.get_details_string()
                group_elements = [comp_C]
            elif selected_type == "RL (Série)":
                comp_R = Resistor(R)
                comp_L = Inductor(L)
                group_impedance = impedancia_serie([comp_R.calculate_impedance(freq_angular), comp_L.calculate_impedance(freq_angular)])
                group_details_str = f"{comp_R.get_details_string()}, {comp_L.get_details_string()}"
                group_elements = [comp_R, comp_L]
            elif selected_type == "RC (Série)":
                comp_R = Resistor(R)
                comp_C = Capacitor(C)
                group_impedance = impedancia_serie([comp_R.calculate_impedance(freq_angular), comp_C.calculate_impedance(freq_angular)])
                group_details_str = f"{comp_R.get_details_string()}, {comp_C.get_details_string()}"
                group_elements = [comp_R, comp_C]
            elif selected_type == "RLC (Série)":
                comp_R = Resistor(R)
                comp_L = Inductor(L)
                comp_C = Capacitor(C)
                group_impedance = impedancia_serie([comp_R.calculate_impedance(freq_angular), comp_L.calculate_impedance(freq_angular), comp_C.calculate_impedance(freq_angular)])
                group_details_str = f"{comp_R.get_details_string()}, {comp_L.get_details_string()}, {comp_C.get_details_string()}"
                group_elements = [comp_R, comp_L, comp_C]
            elif selected_type == "Z Conhecida":
                comp_Z = ImpedanciaConhecida(Z_mag, Z_angle)
                group_impedance = comp_Z.calculate_impedance(freq_angular)
                group_details_str = comp_Z.get_details_string()
                group_elements = [comp_Z] 

            self.group_counter += 1
            group_display_name = f"Grupo {self.group_counter} ({selected_type})"
            
            messagebox.showinfo("Grupo Calculado", 
                                 f"{group_display_name} - Impedância: {complex_to_polar_str(group_impedance)}")
            
            self.calculated_group_info = {
                'name': group_display_name,
                'type': selected_type, 
                'impedance': group_impedance,
                'details': group_details_str,
                'circuit_group_object': CircuitGroup('series', name=group_display_name)
            }
            for elem in group_elements:
                self.calculated_group_info['circuit_group_object'].add_element(elem)

            for _, entry_widget in self.labels_entries.values():
                entry_widget.delete(0, tk.END)

        except ValueError as e:
            messagebox.showerror("Erro de Entrada", f"Verifique os valores inseridos para o grupo.\nErro: {e}")
        except Exception as e:
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro inesperado ao calcular o grupo: {e}")

    def add_group_to_final_circuit(self, connection_type):
        if self.calculated_group_info is None:
            messagebox.showwarning("Grupo Necessário", "Calcule a impedância de um grupo primeiro.")
            return
        
        group_info = self.calculated_group_info
        current_group_object = group_info['circuit_group_object']
        
        if self.group_counter == 1 and not self.root_circuit_group.elements: # Primeiro grupo adicionado ao circuito (ou resetado)
            self.root_circuit_group.elements = [current_group_object]
            self.root_circuit_group.group_type = connection_type
            connection_description = "Início"
        else:
            new_root = CircuitGroup(connection_type, name="Circuito Principal")
            new_root.add_element(self.root_circuit_group)
            new_root.add_element(current_group_object)
            self.root_circuit_group = new_root
            connection_description = connection_type.capitalize()

        V_source_rms, freq_hz, freq_angular = self.get_common_params()
        if V_source_rms is None: return
        self.final_impedance = self.root_circuit_group.calculate_impedance(freq_angular)

        self.circuit_history.append({
            'group_name': group_info['name'],
            'connection_type': connection_description,
            'group_impedance': group_info['impedance'],
            'total_impedance_after': self.final_impedance,
            'details': group_info['details']
        })
        
        self.calculated_group_info = None
        self.update_history_display() 
        self.update_final_impedance_display()
        self.calculate_and_display_results()
        
        self.calculate_all_voltages_and_currents()

    def update_history_display(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        for record in self.circuit_history:
            self.history_tree.insert("", "end", values=(
                record['group_name'],
                record['connection_type'],
                complex_to_polar_str(record['total_impedance_after']),
                f"{record['details']} (Z_grupo={complex_to_polar_str(record['group_impedance'])})"
            ))

    def update_final_impedance_display(self):
        self.final_impedance_label.config(text=f"Z_total: {complex_to_polar_str(self.final_impedance)}")

    def calculate_and_display_results(self):
        V_source_rms, freq_hz, freq_angular = self.get_common_params()
        if V_source_rms is None: 
            self.clear_results()
            return

        try:
            total_Z = self.final_impedance

            if abs(total_Z) < 1e-9:
                self.result_labels["Corrente Total (I_total):"].config(text="Infinito < 0.00° A (Curto-circuito)")
                for label_text in ["Potência Ativa (P):", "Potência Reativa (Q):", "Potência Aparente (S):", "Fator de Potência (FP):"]:
                    self.result_labels[label_text].config(text="Não Aplicável")
                self.V_source_fasor = cmath.rect(V_source_rms, math.radians(0))
                self.I_total_fasor = complex(float('inf'), 0)
                return 
            elif abs(total_Z) == float('inf'):
                self.result_labels["Corrente Total (I_total):"].config(text="0.0000 < 0.00° A (Circuito Aberto)")
                for label_text in ["Potência Ativa (P):", "Potência Reativa (Q):", "Potência Aparente (S):", "Fator de Potência (FP):"]:
                    self.result_labels[label_text].config(text="Não Aplicável")
                self.V_source_fasor = cmath.rect(V_source_rms, math.radians(0))
                self.I_total_fasor = complex(0, 0)
                return
            
            self.V_source_fasor = cmath.rect(V_source_rms, math.radians(0))
            self.I_total_fasor = self.V_source_fasor / total_Z

            P, Q, S_aparente, fp, S_complexa = calcular_potencia_complexa(self.V_source_fasor, self.I_total_fasor)

            self.result_labels["Corrente Total (I_total):"].config(text=complex_to_polar_str(self.I_total_fasor))
            self.result_labels["Potência Ativa (P):"].config(text=f"{P:.4f} W")
            self.result_labels["Potência Reativa (Q):"].config(text=f"{Q:.4f} VAR")
            self.result_labels["Potência Aparente (S):"].config(text=f"{S_aparente:.4f} VA")
            self.result_labels["Fator de Potência (FP):"].config(text=f"{fp:.4f} {'(Atrasado)' if Q > 0 else ('(Adiantado)' if Q < 0 else '(Unitário)')}")

        except ValueError as e:
            messagebox.showerror("Erro de Cálculo", f"Erro de cálculo: {e}")
            self.clear_results()
        except ZeroDivisionError as e:
            messagebox.showerror("Erro de Cálculo", f"Erro de divisão por zero: {e}\nIsso pode ocorrer se a impedância total for zero.")
            self.clear_results()
        except Exception as e:
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro inesperado: {e}")
            self.clear_results()

    def calculate_total_impedance_at_frequency(self, freq_angular):
        """
        Calcula a impedância total do circuito montado em uma dada frequência angular
        percorrendo a árvore `self.root_circuit_group`.
        """
        if not self.root_circuit_group.elements:
            return complex(0,0)
        return self.root_circuit_group.calculate_impedance(freq_angular)

    def plot_frequency_response(self):
        if not self.root_circuit_group.elements:
            messagebox.showwarning("Circuito Vazio", "Adicione componentes ao circuito para plotar a resposta em frequência.")
            return

        f_min = 1 
        f_max = 1e6 
        num_points = 200 

        freq_base_hz = float(self.f_entry.get() or 60)
        
        f_min = max(1, freq_base_hz / 100)
        f_max = freq_base_hz * 100

        frequencies_hz = np.logspace(np.log10(f_min), np.log10(f_max), num_points)
        magnitudes_db = []
        
        for f_hz in frequencies_hz:
            omega = 2 * math.pi * f_hz
            
            try:
                Z_total_at_f = self.calculate_total_impedance_at_frequency(omega)
                
                if abs(Z_total_at_f) == float('inf'): 
                    magnitude_db = 100 
                elif abs(Z_total_at_f) < 1e-12: 
                    magnitude_db = -100 
                else:
                    magnitude_db = 20 * np.log10(abs(Z_total_at_f))
                
                magnitudes_db.append(magnitude_db)
            except Exception as e:
                magnitudes_db.append(np.nan) 

        plt.figure(figsize=(10, 6))
        plt.semilogx(frequencies_hz, magnitudes_db) 
        plt.title('Diagrama de Magnitude de Bode da Impedância Total')
        plt.xlabel('Frequência (Hz, escala logarítmica)')
        plt.ylabel('Magnitude da Impedância (dB)')
        plt.grid(True, which="both", ls="-", color='0.7')
        plt.axvline(x=freq_base_hz, color='r', linestyle='--', label=f'Frequência Base: {freq_base_hz:.2f} Hz')
        plt.legend()
        plt.tight_layout()
        plt.show()

    def calculate_all_voltages_and_currents(self):
        """
        Calcula as tensões e correntes de todos os componentes no circuito principal.
        """
        self.all_component_phasors = []

        V_source_rms, freq_hz, freq_angular = self.get_common_params()
        if V_source_rms is None: return

        if not self.root_circuit_group.elements:
            return

        total_Z = self.root_circuit_group.calculate_impedance(freq_angular)
        if abs(total_Z) < 1e-9 or abs(total_Z) == float('inf'):
            return

        self.V_source_fasor = cmath.rect(V_source_rms, math.radians(0))
        self.I_total_fasor = self.V_source_fasor / total_Z

        self.all_component_phasors.append({'label': 'V_fonte', 'phasor': self.V_source_fasor, 'color': 'blue'})
        self.all_component_phasors.append({'label': 'I_total', 'phasor': self.I_total_fasor, 'color': 'red'})

        self._propagate_phasors(self.root_circuit_group, self.V_source_fasor, self.I_total_fasor, freq_angular)

    def _propagate_phasors(self, current_element, voltage_across_element, current_through_element, freq_angular):
        """
        Função recursiva para calcular tensões e correntes em sub-elementos.
        """
        current_element.voltage = voltage_across_element
        current_element.current = current_through_element
        
        current_element_Z = current_element.calculate_impedance(freq_angular)

        if isinstance(current_element, Component):
            self.all_component_phasors.append({
                'label': f"V_{current_element.name}",
                'phasor': current_element.voltage,
                'color': 'darkgreen'
            })
            self.all_component_phasors.append({
                'label': f"I_{current_element.name}",
                'phasor': current_element.current,
                'color': 'purple'
            })
            return

        if isinstance(current_element, CircuitGroup):
            if current_element.group_type == 'series':
                for child_element in current_element.elements:
                    child_current = current_through_element
                    child_impedance = child_element.calculate_impedance(freq_angular)
                    child_voltage = child_current * child_impedance
                    
                    self._propagate_phasors(child_element, child_voltage, child_current, freq_angular)

            elif current_element.group_type == 'parallel':
                for child_element in current_element.elements:
                    child_voltage = voltage_across_element
                    child_impedance = child_element.calculate_impedance(freq_angular)
                    if abs(child_impedance) < 1e-9:
                        child_current = complex(float('inf'), 0)
                    elif abs(child_impedance) == float('inf'):
                        child_current = complex(0, 0)
                    else:
                        child_current = child_voltage / child_impedance
                    
                    self._propagate_phasors(child_element, child_voltage, child_current, freq_angular)

    def plot_all_phasors_diagram(self):
        if not self.all_component_phasors:
            messagebox.showwarning("Dados Insuficientes", "Calcule o circuito primeiro para obter todos os fasores.")
            return

        max_magnitude = 0
        for item in self.all_component_phasors:
            if abs(item['phasor']) != float('inf'):
                max_magnitude = max(max_magnitude, abs(item['phasor']))
        
        if max_magnitude == 0:
            max_magnitude = 1 
        
        padding = max_magnitude * 0.2
        lim = max_magnitude + padding

        fig, ax = plt.subplots(figsize=(8, 8))

        for item in self.all_component_phasors:
            phasor = item['phasor']
            label = item['label']
            color = item.get('color', 'black')

            if abs(phasor) == float('inf'):
                continue 

            ax.arrow(0, 0, phasor.real, phasor.imag,
                     head_width=lim*0.02, head_length=lim*0.03, fc=color, ec=color, linewidth=1.5)
            ax.text(phasor.real * 1.05, phasor.imag * 1.05,
                    f'{label} ({complex_to_polar_str(phasor)})', color=color, fontsize=8)

        ax.set_title('Diagrama Fasorial Completo')
        ax.set_xlabel('Parte Real')
        ax.set_ylabel('Parte Imaginária')
        ax.grid(True)
        ax.axhline(0, color='gray', linewidth=0.5)
        ax.axvline(0, color='gray', linewidth=0.5)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xlim([-lim, lim])
        ax.set_ylim([-lim, lim])
        plt.tight_layout()
        plt.show()

# --- Execução da Aplicação ---
if __name__ == "__main__":
    root = tk.Tk()
    app = CalculadoraCircuitosPorGrupo(root)
    root.mainloop()