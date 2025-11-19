import tkinter as tk
from tkinter import ttk, messagebox
import cmath # Para operações com números complexos
import math  # Para funções matemáticas como graus e radianos
import numpy as np # Para arrays e operações numéricas, especialmente para plotagem
import matplotlib.pyplot as plt # Para plotagem de gráficos
import datetime
import ttkbootstrap as ttkb # <--- IMPORTAÇÃO NOVA
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from tkinter import filedialog
from fpdf import FPDF

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

def parse_unit_input(value_str):
    """
    Converte strings com unidades de engenharia (m, u, n, p, k, M) para valores base SI.
    Ex: '10m' -> 0.01; '47u' -> 0.000047
    """
    if not value_str:
        return 0.0

    # Remove qualquer caractere de unidade (F, H, Ohm) para simplificar a leitura
    value_str = value_str.lower().strip().replace('f', '').replace('h', '').replace('ohm', '')

    multipliers = {
        'p': 1e-12,  # pico
        'n': 1e-9,   # nano
        'u': 1e-6,   # micro
        'm': 1e-3,   # mili
        'k': 1e3,    # quilo
        'meg': 1e6   # mega
    }
    
    unit_char = value_str[-1] if value_str[-1].isalpha() and value_str[-1] in multipliers else ''
    
    if unit_char:
        try:
            numeric_part = float(value_str[:-1])
            return numeric_part * multipliers[unit_char]
        except ValueError:
            # Caso a parte numérica falhe após remover a unidade
            pass
    
    try:
        # Se não houver unidade ou se for inválida, tenta converter diretamente
        return float(value_str)
    except ValueError:
        # Retorna erro se a string inteira não for um número
        raise ValueError(f"Entrada inválida para unidade: '{value_str}'")
    
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
        self.voltage = None

class Component:
    """Classe base para componentes individuais (R, L, C, Z Conhecida)."""
    def __init__(self, value, name="Componente"):
        self.value = value
        self.name = name
        self.impedance = None
        self.voltage = None
        self.current = None
        self.node_pos = None
        self.node_neg = None

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
        self.group_type = group_type
        self.name = name
        self.elements = []
        self.impedance = None
        self.voltage = None
        self.current = None

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
        if not impedances: return complex(0, -float('inf')) 
        if any(abs(z) < 1e-9 for z in impedances):
            return complex(0, 0)

        valid_impedances = [z for z in impedances if abs(z) != float('inf')]
        if not valid_impedances: return complex(0, -float('inf'))

        try:
            sum_inverses = sum(1/z for z in valid_impedances)
            if abs(sum_inverses) < 1e-9: return complex(0, -float('inf'))
            return 1 / sum_inverses
        except ZeroDivisionError:
            return complex(0, 0)

    def get_details_string(self):
        elem_details = ", ".join([e.get_details_string() for e in self.elements])
        return f"{self.group_type.capitalize()} Grupo: [{elem_details}]"

    def __repr__(self):
        return self.name

# --------------------------------------------------------------------------------
# --- CLASSE PARA FUNCIONALIDADE DE ARRASTAR RÓTULOS (CORREÇÃO DE ESTRUTURA) ---
# --------------------------------------------------------------------------------
class DraggableAnnotation:
    """Permite clicar e arrastar um objeto de texto (Annotation) no Matplotlib."""
    def __init__(self, annotation):
        self.annotation = annotation
        self.press_cid = None
        self.release_cid = None
        self.motion_cid = None
        self.press_x = None
        self.press_y = None
        self.press_annotation_x = None
        self.press_annotation_y = None
        self.canvas = annotation.figure.canvas
        self.connect()

    def connect(self):
        """Conecta eventos do mouse."""
        self.press_cid = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.release_cid = self.canvas.mpl_connect('button_release_event', self.on_release)

    def on_press(self, event):
        """Verifica se o clique está no rótulo."""
        if event.inaxes != self.annotation.axes: return
        
        contains, attr = self.annotation.contains(event) 
        if not contains: return # Se não clicou no rótulo, sai.
        
        # ⚠️ AJUSTE CRUCIAL: Permite clique com o botão esquerdo (1) ou do meio (2).
        if event.button not in [1, 2]: return 
        
        # Inicia o arrasto
        self.press_x = event.xdata # Coordenada do clique no eixo
        self.press_y = event.ydata
        self.press_annotation_x, self.press_annotation_y = self.annotation.get_position()
        self.motion_cid = self.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_motion(self, event):
        """Calcula o novo offset durante o arrasto."""
        if self.press_x is None: return
        
        dx = event.xdata - self.press_x
        dy = event.ydata - self.press_y
        
        new_x = self.press_annotation_x + dx
        new_y = self.press_annotation_y + dy
        
        self.annotation.set_position((new_x, new_y))
        self.canvas.draw_idle()

    def on_release(self, event):
        """Finaliza o evento de arrasto."""
        if self.motion_cid is not None:
            self.canvas.mpl_disconnect(self.motion_cid)
        self.motion_cid = None
        self.press_x = None
        self.press_y = None
        self.press_annotation_x = None
        self.press_annotation_y = None
        
    def disconnect(self):
        """Desconecta todos os eventos."""
        self.canvas.mpl_disconnect(self.press_cid)
        self.canvas.mpl_disconnect(self.release_cid)
        if self.motion_cid is not None:
            self.canvas.mpl_disconnect(self.motion_cid)

# --------------------------------------------------------------------------------
# --- Lógica da Interface Gráfica ---
# --------------------------------------------------------------------------------

class CalculadoraCircuitosPorGrupo:
    def __init__(self, master):
        self.master = master
        master.title("Calculadora de Circuitos CA (Completa)")
        
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
        self.draggable_annotations = [] 
        
        # --- VARIÁVEIS DE FILTRO (Adicionadas para resolver o AttributeError) ---
        self.show_voltage_phasors = tk.BooleanVar(master, value=True) 
        self.show_current_phasors = tk.BooleanVar(master, value=True) 
        # -----------------------------------------------------------------------

        self.create_widgets(self.scrollable_frame)
        self.reset_circuit()

    def generate_report_content(self):
        """Compila todos os resultados e o histórico de cálculos em um formato de texto."""
        
        # Recebe os 4 parâmetros (incluindo ângulo)
        V_source_rms, freq_hz, freq_angular, angle_source_deg = self.get_common_params()
        
        if V_source_rms is None:
            return "Erro: Parâmetros de Tensão/Frequência inválidos para gerar relatório.\n"

        content = f"=================================================================\n"
        content += f"                RELATÓRIO DE CÁLCULO DE CIRCUITO CA\n"
        content += f"=================================================================\n"
        content += f"Data e Hora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"-----------------------------------------------------------------\n"
        # --- SEÇÃO ASCII REMOVIDA DAQUI ---
        content += f"PARÂMETROS DE ENTRADA\n"
        content += f"Tensão da Fonte (V_rms): {V_source_rms} V @ {angle_source_deg}°\n"
        content += f"Frequência Base (f): {freq_hz} Hz\n"
        content += f"Frequência Angular (ω): {freq_angular:.4f} rad/s\n"
        content += f"-----------------------------------------------------------------\n"

        content += f"HISTÓRICO DE REDUÇÃO (PROVA DO CÁLCULO)\n"
        if not self.circuit_history:
            content += "Nenhum grupo adicionado.\n"
        else:
            for i, record in enumerate(self.circuit_history):
                content += f"  {i+1}. Grupo: {record['group_name']}\n"
                content += f"     - Elementos: {record['details']}\n"
                content += f"     - Conexão: {record['connection_type']}\n"
                content += f"     - Z do Grupo: {complex_to_polar_str(record['group_impedance'])}\n"
                content += f"     - Z TOTAL Acumulada: {complex_to_polar_str(record['total_impedance_after'])}\n"
        content += f"-----------------------------------------------------------------\n"
        
        if self.I_total_fasor and abs(self.final_impedance) not in [0, float('inf')]:
            P, Q, S_aparente, fp, S_complexa = calcular_potencia_complexa(self.V_source_fasor, self.I_total_fasor)
            
            content += f"RESULTADOS FINAIS NA FREQUÊNCIA BASE\n"
            content += f"Z Total Final: {complex_to_polar_str(self.final_impedance)} Ω\n"
            content += f"I Total: {complex_to_polar_str(self.I_total_fasor)} A\n"
            content += f"Potência Ativa (P): {P:.4f} W\n"
            content += f"Potência Reativa (Q): {Q:.4f} VAR ({'Indutivo' if Q > 0 else 'Capacitivo' if Q < 0 else 'Unitário'})\n"
            content += f"Potência Aparente (S): {S_aparente:.4f} VA\n"
            content += f"Fator de Potência (FP): {fp:.4f}\n"
        else:
             content += f"RESULTADOS FINAIS NA FREQUÊNCIA BASE\n"
             content += f"Z Total Final: {complex_to_polar_str(self.final_impedance)} Ω\n"
             content += "Cálculos de potência e corrente não disponíveis (curto ou aberto).\n"

        content += f"=================================================================\n"
        return content
    
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
        # --- Atalho de Teclado ---
        self.master.bind('<Return>', lambda event: self.calculate_group_impedance())

        # --- Frame de Parâmetros Gerais ---
        general_params_frame = ttk.LabelFrame(parent_frame, text="Parâmetros da Fonte e Frequência", padding="10")
        general_params_frame.pack(padx=10, pady=5, fill="x", expand=False)

        ttk.Label(general_params_frame, text="Tensão da Fonte (V_rms) [V]:").grid(row=0, column=0, sticky="w", pady=2)
        self.v_source_entry = ttk.Entry(general_params_frame, width=10)
        self.v_source_entry.grid(row=0, column=1, sticky="w", pady=2, padx=5)
        self.v_source_entry.insert(0, "120")

        ttk.Label(general_params_frame, text="Ângulo da Fonte (°):").grid(row=0, column=2, sticky="w", pady=2, padx=5)
        self.v_angle_entry = ttk.Entry(general_params_frame, width=10)
        self.v_angle_entry.grid(row=0, column=3, sticky="w", pady=2, padx=5)
        self.v_angle_entry.insert(0, "0")

        ttk.Label(general_params_frame, text="Frequência Base (f) [Hz]:").grid(row=1, column=0, sticky="w", pady=2)
        self.f_entry = ttk.Entry(general_params_frame, width=10)
        self.f_entry.grid(row=1, column=1, sticky="w", pady=2, padx=5)
        self.f_entry.insert(0, "60")
        
        # --- Frame para Definir Grupos ---
        define_group_frame = ttk.LabelFrame(parent_frame, text="Definir Novo Grupo", padding="10")
        define_group_frame.pack(padx=10, pady=5, fill="x", expand=False)
        
        # --- MELHORIA VISUAL 1: LEGENDA DE UNIDADES ---
        # Usamos bootstyle="info" para ficar AZUL CLARO brilhante e legível
        units_guide_label = ttk.Label(define_group_frame, 
            text="DICA: Use sufixos como 'm' (mili), 'u' (micro), 'k' (quilo) nos valores abaixo.",
            bootstyle="info", # <--- MUDANÇA AQUI: Cor automática do tema (Ciano)
            font=("Segoe UI", 9)) # Fonte mais limpa
        units_guide_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        # ------------------------------------------------
        
        ttk.Label(define_group_frame, text="Tipo de Grupo:").grid(row=1, column=0, sticky="w", pady=2)
        self.group_type_var = tk.StringVar(parent_frame) 
        self.group_type_combo = ttk.Combobox(define_group_frame, textvariable=self.group_type_var,
                                             values=[
                                                 "R", "L", "C", 
                                                 "RL (Série)", "RC (Série)", "RLC (Série)",
                                                 "RL (Paralelo)", "RC (Paralelo)", "RLC (Paralelo)",
                                                 "Z Conhecida"
                                             ])
        self.group_type_combo.grid(row=1, column=1, sticky="ew", pady=2)
        self.group_type_combo.set("R")
        self.group_type_combo.bind("<<ComboboxSelected>>", self.on_group_type_select)

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
            label.grid(row=i+2, column=0, sticky="w", pady=2)
            entry = ttk.Entry(define_group_frame)
            entry.grid(row=i+2, column=1, sticky="ew", pady=2)
            self.labels_entries[var_name] = (label, entry)
        
        self.define_group_button = ttk.Button(define_group_frame, text="Calcular Impedância do Grupo (Enter)", command=self.calculate_group_impedance)
        self.define_group_button.grid(row=len(fields)+3, column=0, columnspan=2, pady=5, sticky="ew")
        ToolTip(self.define_group_button, "Processa os valores acima e prepara o grupo para ser adicionado.")

        # --- Frame para Adicionar Grupo ---
        add_to_final_frame = ttk.LabelFrame(parent_frame, text="Adicionar Grupo Calculado ao Circuito Final", padding="10")
        add_to_final_frame.pack(padx=10, pady=5, fill="x", expand=False)
        
        # --- MELHORIA VISUAL 2: LEGENDA DE HIERARQUIA ---
        # Usamos bootstyle="warning" para ficar LARANJA brilhante (atenção)
        hierarchy_guide_label = ttk.Label(add_to_final_frame, 
            text="Atenção: A conexão é feita entre o NOVO Grupo e o Total Acumulado.",
            bootstyle="warning", # <--- MUDANÇA AQUI: Cor de alerta (Laranja)
            font=("Segoe UI", 9))
        hierarchy_guide_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        # ------------------------------------------------

        btn_series = ttk.Button(add_to_final_frame, text="Adicionar em Série", command=lambda: self.add_group_to_final_circuit('series'))
        btn_series.grid(row=1, column=0, sticky="ew", padx=2, pady=5)
        ToolTip(btn_series, "Soma a impedância do novo grupo à impedância total atual.")

        btn_parallel = ttk.Button(add_to_final_frame, text="Adicionar em Paralelo", command=lambda: self.add_group_to_final_circuit('parallel'))
        btn_parallel.grid(row=1, column=1, sticky="ew", padx=2, pady=5)
        ToolTip(btn_parallel, "Coloca o novo grupo em paralelo com todo o circuito acumulado até agora.")

        # --- Histórico ---
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
        
        final_impedance_frame = ttk.LabelFrame(parent_frame, text="Impedância Total do Circuito", padding="10")
        final_impedance_frame.pack(padx=10, pady=5, fill="x", expand=False)
        self.final_impedance_label = ttk.Label(final_impedance_frame, text="Z_total: ")
        self.final_impedance_label.pack(fill="x")
        
        # --- Gráficos e Visualização ---
        self.plot_container_frame = ttk.LabelFrame(parent_frame, text="Visualização do Circuito (Gráficos Interativos)", padding="10")
        self.plot_container_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.canvas_widget = None; self.toolbar_widget = None

        plot_btns = ttk.Frame(self.plot_container_frame)
        plot_btns.pack(pady=5)
        
        b1 = ttk.Button(plot_btns, text="Plotar Bode", command=self.plot_frequency_response)
        b1.pack(side=tk.LEFT, padx=5)
        ToolTip(b1, "Gráfico de Magnitude (dB) vs Frequência (Hz).")
        
        b2 = ttk.Button(plot_btns, text="Plotar Diagrama Fasorial", command=self.plot_all_phasors_diagram)
        b2.pack(side=tk.LEFT, padx=5)
        ToolTip(b2, "Mostra vetores de Tensão e Corrente no plano complexo.")

        b3 = ttk.Button(plot_btns, text="Plotar Potências", command=self.plot_power_triangle)
        b3.pack(side=tk.LEFT, padx=5)
        ToolTip(b3, "Exibe o Triângulo de Potências (Ativa, Reativa, Aparente).")

        b4 = ttk.Button(plot_btns, text="Habilitar Arrasto", command=self.activate_label_drag_mode)
        b4.pack(side=tk.LEFT, padx=5)
        ToolTip(b4, "Desliga o zoom do gráfico para permitir arrastar as legendas.")

        # --- Resultados Finais ---
        results_frame = ttk.LabelFrame(parent_frame, text="Resultados Finais do Circuito na Frequência Base", padding="10")
        results_frame.pack(padx=10, pady=5, fill="x", expand=False)

        self.result_labels = {}
        result_texts = ["Corrente Total (I_total):", "Potência Ativa (P):", "Potência Reativa (Q):", "Potência Aparente (S):", "Fator de Potência (FP):"]

        for i, text in enumerate(result_texts):
            ttk.Label(results_frame, text=text).grid(row=i, column=0, sticky="w", pady=2)
            value_label = ttk.Label(results_frame, text="")
            value_label.grid(row=i, column=1, sticky="w", pady=2)
            self.result_labels[text] = value_label

        # --- Filtros de Fasores ---
        filter_params_frame = ttk.LabelFrame(parent_frame, text="Filtro do Diagrama Fasorial", padding="10")
        filter_params_frame.pack(padx=10, pady=5, fill="x", expand=False)
        
        c1 = ttk.Checkbutton(filter_params_frame, text="Mostrar Tensões (V)", variable=self.show_voltage_phasors, onvalue=True, offvalue=False)
        c1.grid(row=0, column=0, sticky="w", padx=10)
        ToolTip(c1, "Ativa/Desativa os vetores de tensão no gráfico.")

        c2 = ttk.Checkbutton(filter_params_frame, text="Mostrar Correntes (I)", variable=self.show_current_phasors, onvalue=True, offvalue=False)
        c2.grid(row=0, column=1, sticky="w", padx=10)
        ToolTip(c2, "Ativa/Desativa os vetores de corrente no gráfico.")

        # --- Botão Reset e Relatório ---
        report_buttons_frame = ttk.Frame(parent_frame)
        report_buttons_frame.pack(pady=10)
        
        btn_report = ttk.Button(report_buttons_frame, text="Gerar Relatório", command=self.save_report_to_file)
        btn_report.pack(side=tk.LEFT, padx=5)
        ToolTip(btn_report, "Salva um arquivo TXT ou PDF com todos os cálculos.")

        btn_reset = ttk.Button(report_buttons_frame, text="Resetar Circuito", command=self.reset_circuit)
        btn_reset.pack(side=tk.LEFT, padx=5)
        ToolTip(btn_reset, "Apaga todo o circuito atual e reinicia.")

        self.on_group_type_select()
    def save_report_to_file(self):
        """Abre a caixa de diálogo e salva o conteúdo do relatório em PDF ou TXT."""
        
        report_content = self.generate_report_content()
        
        if not report_content:
            messagebox.showwarning("Relatório Vazio", "Nenhum cálculo efetuado para gerar relatório.")
            return

        # Configura a caixa de diálogo para sugerir PDF por padrão
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Arquivo PDF", "*.pdf"), ("Arquivo de Texto", "*.txt")],
            title="Salvar Relatório de Circuito"
        )

        if not file_path:
            return

        try:
            if file_path.lower().endswith('.pdf'):
                # --- GERAÇÃO DE PDF ---
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=10)
                
                # Título
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt="Relatorio de Calculo de Circuito CA", ln=1, align='C')
                pdf.ln(10) # Pula linha
                
                # Conteúdo
                pdf.set_font("Courier", size=10) # Courier é bom para alinhar números
                
                # --- LIMPEZA DE CARACTERES ESPECIAIS (Correção do Erro) ---
                # O FPDF padrão não aceita Unicode completo. Substituímos por texto seguro.
                safe_content = report_content.replace("Ω", "Ohm") \
                                             .replace("°", "deg") \
                                             .replace("μ", "u") \
                                             .replace("ω", "w") \
                                             .replace("∠", "<")
                # ----------------------------------------------------------
                
                # Usa multi_cell para quebra de linha automática
                pdf.multi_cell(0, 5, txt=safe_content)
                
                pdf.output(file_path)
                
            else:
                # --- GERAÇÃO DE TXT (Fallback - Suporta tudo via utf-8) ---
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)

            messagebox.showinfo("Sucesso", f"Relatório salvo com sucesso em:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}")        
    def activate_label_drag_mode(self):
        """Desliga Pan e Zoom nativos do Matplotlib para garantir que o arrasto personalizado funcione."""
        if self.toolbar_widget:
            # Chama .pan() e .zoom() sem argumentos para desativar qualquer modo ativo.
            # Isso garante que o Matplotlib pare de sequestrar o evento de clique do botão esquerdo.
            self.toolbar_widget.pan()
            self.toolbar_widget.zoom()
            
            # Força o Matplotlib a redesenhar para que o modo seja desligado
            self.toolbar_widget.canvas.draw_idle() 
            
            messagebox.showinfo("Arrasto Habilitado", 
                                "Os modos Pan/Zoom nativos foram desativados.\nAgora, use o botão esquerdo para clicar e arrastar os rótulos.")
        else:
            messagebox.showwarning("Erro", "Plote o diagrama fasorial primeiro.")

    def reset_circuit(self):
        self.root_circuit_group = CircuitGroup('series', name="Circuito Principal")
        self.final_impedance = complex(0,0)
        self.group_counter = 0
        self.calculated_group_info = None
        self.circuit_history = []
        self.all_component_phasors = []
        self.V_source_fasor = complex(0,0)
        self.I_total_fasor = complex(0,0)
        self.draggable_annotations = []

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
            angle_source_deg = float(self.v_angle_entry.get()) # Lê o ângulo
            freq_hz = float(self.f_entry.get())
            if freq_hz <= 0:
                raise ValueError("A frequência deve ser maior que zero.")
            freq_angular = 2 * math.pi * freq_hz
            # Retorna agora 4 valores
            return V_source_rms, freq_hz, freq_angular, angle_source_deg
        except ValueError as e:
            messagebox.showerror("Erro de Entrada", f"Verifique os valores de tensão, ângulo ou frequência.\nErro: {e}")
            return None, None, None, None

    def on_group_type_select(self, event=None):
        selected_type = self.group_type_var.get()
        
        for label_widget, entry_widget in self.labels_entries.values():
            entry_widget.config(state=tk.DISABLED)
            entry_widget.delete(0, tk.END) 
        
        # Lógica simplificada: Se tem 'R' no nome, ativa campo R, etc.
        if "R" in selected_type or selected_type == "R":
            self.labels_entries["r_val"][1].config(state=tk.NORMAL)
        if "L" in selected_type or selected_type == "L":
            self.labels_entries["l_val"][1].config(state=tk.NORMAL)
        if "C" in selected_type or selected_type == "C":
            self.labels_entries["c_val"][1].config(state=tk.NORMAL)
            
        if selected_type == "Z Conhecida":
            self.labels_entries["z_mag_val"][1].config(state=tk.NORMAL)
            self.labels_entries["z_angle_val"][1].config(state=tk.NORMAL)

    def calculate_group_impedance(self):
        # Atualizado para receber o ângulo (mesmo que não use aqui, precisa desempacotar)
        V_source_rms, freq_hz, freq_angular, _ = self.get_common_params()
        if V_source_rms is None: return

        selected_type = self.group_type_var.get()
        group_impedance = complex(0,0)
        group_details_str = "" 
        group_elements = []

        try:
            R = parse_unit_input(self.labels_entries["r_val"][1].get())
            L = parse_unit_input(self.labels_entries["l_val"][1].get())
            C = parse_unit_input(self.labels_entries["c_val"][1].get())
            Z_mag = float(self.labels_entries["z_mag_val"][1].get() or 0)
            Z_angle = float(self.labels_entries["z_angle_val"][1].get() or 0)

            # --- LÓGICA DE CRIAÇÃO DOS GRUPOS ---
            if selected_type == "R":
                comp = Resistor(R); group_impedance = comp.calculate_impedance(freq_angular); group_elements = [comp]
            elif selected_type == "L":
                comp = Inductor(L); group_impedance = comp.calculate_impedance(freq_angular); group_elements = [comp]
            elif selected_type == "C":
                comp = Capacitor(C); group_impedance = comp.calculate_impedance(freq_angular); group_elements = [comp]
            
            # --- SÉRIE ---
            elif "Série" in selected_type:
                comps = []
                if "R" in selected_type: comps.append(Resistor(R))
                if "L" in selected_type: comps.append(Inductor(L))
                if "C" in selected_type: comps.append(Capacitor(C))
                
                group_impedance = impedancia_serie([c.calculate_impedance(freq_angular) for c in comps])
                group_elements = comps
            
            # --- PARALELO (NOVA LÓGICA) ---
            elif "Paralelo" in selected_type:
                comps = []
                if "R" in selected_type: comps.append(Resistor(R))
                if "L" in selected_type: comps.append(Inductor(L))
                if "C" in selected_type: comps.append(Capacitor(C))
                
                # Usamos a lógica da classe CircuitGroup para calcular paralelo
                temp_group = CircuitGroup('parallel')
                for c in comps: temp_group.add_element(c)
                
                group_impedance = temp_group.calculate_impedance(freq_angular)
                group_elements = comps

            elif selected_type == "Z Conhecida":
                comp = ImpedanciaConhecida(Z_mag, Z_angle); group_impedance = comp.calculate_impedance(freq_angular); group_elements = [comp]

            # Finalização
            self.group_counter += 1
            group_display_name = f"Grupo {self.group_counter} ({selected_type})"
            group_details_str = ", ".join([e.get_details_string() for e in group_elements])

            messagebox.showinfo("Grupo Calculado", f"{group_display_name} - Impedância: {complex_to_polar_str(group_impedance)}")
            
            # Define o tipo do CircuitGroup objeto baseado na seleção
            obj_type = 'parallel' if "Paralelo" in selected_type else 'series'
            
            self.calculated_group_info = {
                'name': group_display_name,
                'type': selected_type, 
                'impedance': group_impedance,
                'details': group_details_str,
                'circuit_group_object': CircuitGroup(obj_type, name=group_display_name)
            }
            for elem in group_elements:
                self.calculated_group_info['circuit_group_object'].add_element(elem)

            for _, entry_widget in self.labels_entries.values(): entry_widget.delete(0, tk.END)

        except ValueError as e:
            messagebox.showerror("Erro", f"Verifique valores.\nErro: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro inesperado: {e}")

    def add_group_to_final_circuit(self, connection_type):
        if self.calculated_group_info is None:
            messagebox.showwarning("Grupo Necessário", "Calcule a impedância de um grupo primeiro.")
            return
        
        group_info = self.calculated_group_info
        current_group_object = group_info['circuit_group_object']
        
        if self.group_counter == 1 and not self.root_circuit_group.elements: # Primeiro grupo
            self.root_circuit_group.elements = [current_group_object]
            self.root_circuit_group.group_type = connection_type
            connection_description = "Início"
        else:
            new_root = CircuitGroup(connection_type, name="Circuito Principal")
            new_root.add_element(self.root_circuit_group)
            new_root.add_element(current_group_object)
            self.root_circuit_group = new_root
            connection_description = connection_type.capitalize()

        # --- CORREÇÃO AQUI: Recebe 4 valores (ignora o ângulo com _) ---
        V_source_rms, freq_hz, freq_angular, _ = self.get_common_params()
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

    def _display_plot(self, fig):
        """Limpa o canvas anterior e exibe a nova figura Matplotlib no frame."""
        # Limpar widgets antigos (canvas e toolbar)
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()
        if self.toolbar_widget:
            self.toolbar_widget.destroy()

        # Cria o novo Canvas para a figura
        canvas = FigureCanvasTkAgg(fig, master=self.plot_container_frame)
        canvas.draw()
        
        # Cria a barra de ferramentas (com zoom, pan, etc.)
        toolbar = NavigationToolbar2Tk(canvas, self.plot_container_frame)
        toolbar.update()

        # Empacota os widgets no frame
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Salva as referências para limpeza futura
        self.canvas_widget = canvas
        self.toolbar_widget = toolbar

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
        # Recebe o ângulo agora
        V_source_rms, freq_hz, freq_angular, angle_source_deg = self.get_common_params()
        if V_source_rms is None: 
            self.clear_results(); return

        try:
            total_Z = self.final_impedance
            
            # Converte o ângulo da fonte para radianos
            phase_rad = math.radians(angle_source_deg)
            self.V_source_fasor = cmath.rect(V_source_rms, phase_rad) # Usa o ângulo aqui!

            if abs(total_Z) < 1e-9:
                self.I_total_fasor = complex(float('inf'), 0)
            elif abs(total_Z) == float('inf'):
                self.I_total_fasor = complex(0, 0)
            else:
                self.I_total_fasor = self.V_source_fasor / total_Z

            # ... (restante do código igual: cálculo de potências e exibição) ...
            P, Q, S_aparente, fp, S_complexa = calcular_potencia_complexa(self.V_source_fasor, self.I_total_fasor)

            self.result_labels["Corrente Total (I_total):"].config(text=complex_to_polar_str(self.I_total_fasor))
            self.result_labels["Potência Ativa (P):"].config(text=f"{P:.4f} W")
            self.result_labels["Potência Reativa (Q):"].config(text=f"{Q:.4f} VAR")
            self.result_labels["Potência Aparente (S):"].config(text=f"{S_aparente:.4f} VA")
            self.result_labels["Fator de Potência (FP):"].config(text=f"{fp:.4f} {'(Atrasado)' if Q > 0 else ('(Adiantado)' if Q < 0 else '(Unitário)')}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro de cálculo: {e}")

    def calculate_total_impedance_at_frequency(self, freq_angular):
        """
        Calcula a impedância total do circuito montado em uma dada frequência angular
        percorrendo a árvore `self.root_circuit_group`.
        """
        if not self.root_circuit_group.elements:
            return complex(0,0)
        return self.root_circuit_group.calculate_impedance(freq_angular)
    def plot_power_triangle(self):
        """Plota o triângulo das potências (P, Q, S) no plano complexo."""
        # Verificação inicial: garante que os fasores de V e I foram calculados
        if not self.I_total_fasor or abs(self.final_impedance) == 0 or abs(self.final_impedance) == float('inf'):
            messagebox.showwarning("Dados Insuficientes", "Calcule o circuito primeiro para obter as potências.")
            return

        # 1. Calcular Potência Complexa (S = V * I*)
        S_complexa = self.V_source_fasor * self.I_total_fasor.conjugate()
        P = S_complexa.real
        Q = S_complexa.imag
        S_mag = abs(S_complexa)

        # 2. Configuração do Plot
        fig, ax = plt.subplots(figsize=(7, 6))
        
        # Limites e Padding
        max_val = max(abs(P), abs(Q))
        lim = max(max_val * 1.2, 1) # Garante um limite mínimo de 1

        # 3. Desenhar o Triângulo
        
        # Vetor S (Potência Aparente): Hipotenusa (0,0) até (P, Q)
        ax.arrow(0, 0, P, Q, head_width=max_val * 0.03, head_length=max_val * 0.04, 
                 fc='k', ec='k', linewidth=2, length_includes_head=True, 
                 label=f'S (Aparente) = {S_mag:.2f} VA')
        
        # Vetor P (Potência Ativa): Base (0, 0) até (P, 0)
        ax.plot([0, P], [0, 0], 'r-', linewidth=1.5, label=f'P (Ativa) = {P:.2f} W')
        
        # Vetor Q (Potência Reativa): Altura (P, 0) até (P, Q)
        ax.plot([P, P], [0, Q], 'b--', linewidth=1.5, label=f'Q (Reativa) = {Q:.2f} VAR')

        # 4. Rótulo do Ângulo (Fator de Potência)
        if S_mag > 1e-9:
            angle_rad = cmath.phase(S_complexa)
            angle_deg = math.degrees(angle_rad)
            
            # Posição do ângulo (um pouco para fora do eixo)
            angle_pos_x = P * 0.5 if P > 0 else P * 0.8
            angle_pos_y = 0 if Q > 0 else 0
            
            # Desenha o arco e o rótulo do ângulo theta
            # Use um patch para desenhar um arco simples para visualização (opcional)
            from matplotlib.patches import Arc
            if P > 0:
                 ax.add_patch(Arc((0, 0), P*0.5, P*0.5, angle=0, theta1=0, theta2=angle_deg, color='gray', linewidth=0.5))
            
            ax.text(P * 0.4, Q * 0.1, f'θ = {angle_deg:.2f}°', fontsize=10, ha='center', fontweight='bold')
        
        # 5. Formatação Final
        ax.set_title('Diagrama do Triângulo de Potências')
        ax.set_xlabel('Potência Ativa (W)')
        ax.set_ylabel('Potência Reativa (VAR)')
        ax.grid(True)
        
        # Ajusta eixos para centralizar em 0 e garantir que P e Q estejam visíveis
        ax.set_xlim([-max_val * 0.1, lim])
        ax.set_ylim([-max_val * 0.1, lim]) 
        
        ax.axhline(0, color='gray', linewidth=0.5)
        ax.axvline(0, color='gray', linewidth=0.5)
        ax.legend(loc='lower right')
        ax.set_aspect('equal', adjustable='box') 
        plt.tight_layout()
        
        self._display_plot(fig)

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

        # Recebe os 4 parâmetros (incluindo ângulo), mas só usamos frequência aqui
        _, freq_base_hz, _, _ = self.get_common_params()
        
        # Se get_common_params falhou (retornou None), usa padrão 60Hz
        if freq_base_hz is None: freq_base_hz = 60.0
        
        f_min = max(1, freq_base_hz / 100)
        f_max = freq_base_hz * 100
        num_points = 200 

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
            except Exception:
                magnitudes_db.append(np.nan) 

        # Cria a figura Matplotlib
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.semilogx(frequencies_hz, magnitudes_db) 
        ax.set_title('Diagrama de Magnitude de Bode da Impedância Total')
        ax.set_xlabel('Frequência (Hz, escala logarítmica)')
        ax.set_ylabel('Magnitude da Impedância (dB)')
        ax.grid(True, which="both", ls="-", color='0.7')
        ax.axvline(x=freq_base_hz, color='r', linestyle='--', label=f'Frequência Base: {freq_base_hz:.2f} Hz')
        ax.legend()
        plt.tight_layout()
        
        # Chama a função utilitária para embutir e exibir
        self._display_plot(fig)

    def calculate_all_voltages_and_currents(self):
        """Calcula as tensões e correntes de todos os componentes no circuito principal."""
        self.all_component_phasors = []

        # --- CORREÇÃO AQUI: Recebe 4 valores ---
        V_source_rms, freq_hz, freq_angular, angle_source_deg = self.get_common_params()
        if V_source_rms is None: return

        if not self.root_circuit_group.elements:
            return

        total_Z = self.root_circuit_group.calculate_impedance(freq_angular)
        if abs(total_Z) < 1e-9 or abs(total_Z) == float('inf'):
            return

        # Usa o ângulo da fonte correto
        phase_rad = math.radians(angle_source_deg)
        self.V_source_fasor = cmath.rect(V_source_rms, phase_rad)
        
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

        # 1. Aplicar Filtros
        valid_phasors = [item for item in self.all_component_phasors if abs(item['phasor']) != float('inf')]
        
        filtered_phasors = []
        for item in valid_phasors:
            label = item['label']
            is_voltage = label.startswith('V')
            is_current = label.startswith('I') or label.startswith('I_')

            # Filtra baseado nas caixas de seleção da GUI
            if is_voltage and self.show_voltage_phasors.get():
                filtered_phasors.append(item)
            elif is_current and self.show_current_phasors.get():
                filtered_phasors.append(item)

        if not filtered_phasors:
            messagebox.showinfo("Filtro Ativo", "Nenhum fasor selecionado ou nenhum fasor finito para plotar.")
            return

        # 2. Encontrar as Magnitudes Máximas (Baseado apenas nos fasores filtrados)
        max_v_mag = max([abs(p['phasor']) for p in filtered_phasors if p['label'].startswith('V')]) if [p for p in filtered_phasors if p['label'].startswith('V')] else 1
        max_i_mag = max([abs(p['phasor']) for p in filtered_phasors if p['label'].startswith('I')]) if [p for p in filtered_phasors if p['label'].startswith('I')] else 1

        # Usar a maior magnitude filtrada para definir os limites do gráfico (e a escala de corrente)
        max_overall_mag = max(max_v_mag, max_i_mag)
        
        # 3. Calcular Fator de Escala Visual para Correntes
        if max_i_mag > 1e-9:
            # Escala a corrente para o tamanho máximo da tensão para comparação visual
            current_scale_factor = max_v_mag / max_i_mag
        else:
            current_scale_factor = max_v_mag 

        # 4. Configuração do Plot
        padding = max_overall_mag * 0.1 
        lim = max_overall_mag + padding

        self.draggable_annotations = []
        fig, ax = plt.subplots(figsize=(8, 8))
        
        OFFSET_INICIAL = 1.05 

        # 5. Plotar Fasores FILTRADOS
        for item in filtered_phasors:
            phasor = item['phasor']
            label = item['label']
            color = item.get('color', 'black')

            if label.startswith('I'):
                # Correntes: Aplica o fator de escala visual
                scaled_phasor = phasor * current_scale_factor
                line_style = '--'
                text_label = f'{label} ({complex_to_polar_str(phasor)})'
            else:
                # Tensões: Escala real (1:1)
                scaled_phasor = phasor
                line_style = '-'
                text_label = f'{label} ({complex_to_polar_str(phasor)})'
            
            x_coord = scaled_phasor.real
            y_coord = scaled_phasor.imag

            # Desenha a seta do fasor
            ax.arrow(0, 0, x_coord, y_coord,
                     head_width=lim*0.02, head_length=lim*0.03, 
                     fc=color, ec=color, linewidth=1.5, 
                     linestyle=line_style, length_includes_head=True)
            
            # ADICIONA O RÓTULO COM CAIXA CLICÁVEL
            text_annotation = ax.text(x_coord * OFFSET_INICIAL, y_coord * OFFSET_INICIAL, 
                                      text_label, 
                                      bbox=dict(boxstyle="round,pad=0.2", 
                                                fc=color, alpha=0.2, ec=color), 
                                      color=color, 
                                      fontsize=8, 
                                      ha='center', va='center',
                                      picker=10)
            
            draggable = DraggableAnnotation(text_annotation)
            self.draggable_annotations.append(draggable)

        # 6. Adicionar Título e Informação de Escala
        info_text = (f"Correntes multiplicadas visualmente por: {current_scale_factor:.2f}x\n"
                     f"Ângulos e fase estão corretos. Arraste rótulos para reposicioná-los.")
        
        ax.set_title('Diagrama Fasorial (Escala Normalizada e Arrastável)')
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.05, 0.95, info_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=props)

        # Configurações finais do gráfico
        ax.set_xlabel('Parte Real')
        ax.set_ylabel('Parte Imaginária')
        ax.grid(True, which="both", ls=":", alpha=0.6)
        ax.axhline(0, color='black', linewidth=0.8)
        ax.axvline(0, color='black', linewidth=0.8)
        ax.set_aspect('equal', adjustable='box') 
        ax.set_xlim([-lim, lim])
        ax.set_ylim([-lim, lim])
        
        plt.tight_layout() 
        self._display_plot(fig)

class ToolTip:
    """Cria uma pequena janela de dica (tooltip) ao passar o mouse sobre um widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        "Exibe a dica"
        if self.tip_window or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        "Oculta a dica"
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

# --- Execução da Aplicação ---
if __name__ == "__main__":
    root = ttkb.Window(themename="darkly") # Temas legais: "darkly", "superhero", "cosmo", "flatly"
    # Adicionando um print para garantir que a janela está sendo chamada
    print("Inicializando a Calculadora de Circuitos...") 
    app = CalculadoraCircuitosPorGrupo(root)
    root.mainloop()