# ⚡ Simulador Avançado de Circuitos em CA - Versão 2.0 (Python/Tkinter)

## 🎓 Contexto do Projeto e Evolução

Este projeto começou como um trabalho da disciplina de Circuitos II e evoluiu de um aplicativo funcional (V1) para uma **ferramenta profissional e interativa (V2.0)**. A arquitetura manteve o Python/Tkinter, mas foi totalmente aprimorada com novas bibliotecas para modernizar a interface e adicionar recursos de análise avançada e documentação.

## ✨ Funcionalidades Avançadas na V2.0

### 1. 🎨 Interface de Usuário (UX/UI)
* **Estética Moderna:** Implementação do **`ttkbootstrap`** para aplicar um tema escuro e visualmente agradável, com componentes estilizados no padrão Bootstrap.
* **Interação Avançada:** Integração nativa de `matplotlib` no Tkinter (`FigureCanvasTkAgg`) e adição de **barras de rolagem** para garantir que o conteúdo se ajuste a qualquer tela.
* **Usabilidade:** Adição de **Tooltips (Dicas de Ferramenta)** e **Legendas Visuais coloridas** para guiar o usuário.

### 2. ⚙️ Cálculos e Modelagem de Entrada
* **Unidades de Engenharia:** A função `parse_unit_input` permite que o usuário insira valores de R, L e C usando sufixos comuns de engenharia (pico, nano, micro, mili, quilo), como **`10uF`** ou **`5mH`**.
* **Fasor de Fonte:** Suporte para definição de **ângulo da fonte**, permitindo a análise fasorial completa com grandezas defasadas da referência.

### 3. 📊 Visualização Interativa
* **Gráficos Embutidos:** Plotagem do Diagrama de Bode, Triângulo de Potências e Diagrama Fasorial diretamente na interface principal.
* **Rótulos Arrastáveis:** Funcionalidade única que permite ao usuário **clicar e arrastar os rótulos de fasores (V e I)** no diagrama complexo para evitar sobreposição e melhorar a legibilidade.

### 4. 📄 Documentação e Exportação
* **Relatórios Profissionais:** Implementação da biblioteca **`FPDF`** para gerar e salvar relatórios detalhados da simulação em formato **PDF** ou TXT, incluindo o histórico de redução do circuito.

## ⚙️ Tecnologias Utilizadas

| Componente | Tecnologia | Função |
| :--- | :--- | :--- |
| **GUI Principal** | Python + `tkinter` | Estrutura da janela e widgets. |
| **Estética/Tema** | `ttkbootstrap` | Estilização moderna da interface. |
| **Cálculos de CA** | `cmath`, `numpy` | Operações com números complexos (fasores). |
| **Gráficos** | `matplotlib` | Plotagem científica e interativa. |
| **Relatórios** | `fpdf` | Geração de arquivos PDF de resultados. |

## 🚀 Como Executar o Projeto

### Pré-requisitos
Você precisará do **Python 3.x** e das bibliotecas listadas no `requirements.txt`.

### 1. `requirements.txt` (Conteúdo Final)

Certifique-se de que o arquivo `requirements.txt` esteja na raiz com o seguinte:

```txt
numpy
matplotlib
ttkbootstrap
fpdf
2. Instalar as Dependências
pip install -r requirements.txt

3. Executar o Aplicativo
Renomeie o arquivo de código (import tkinter as tk.py) para algo simples como simulador.py.
python simulador.py