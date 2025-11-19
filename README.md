# ⚡ Simulador Avançado de Circuitos em Corrente Alternada (CA)

## 🎓 Contexto do Projeto

Este projeto consiste em um simulador de circuitos em Corrente Alternada (CA) com análise fasorial, desenvolvido como trabalho prático para a disciplina de **Circuitos Elétricos II** (ou similar) do curso de Engenharia da Computação. O foco é permitir que o usuário construa circuitos complexos através da adição sequencial de grupos (série ou paralelo) e visualize os resultados completos da simulação na frequência base.

A interface gráfica (GUI) foi construída com **Tkinter**, e as análises gráficas (Bode e Fasorial) utilizam a biblioteca **Matplotlib**.

## ✨ Funcionalidades Principais

O simulador implementa a lógica necessária para o cálculo de grandezas elétricas no domínio fasorial:

* **Construção de Circuitos:** Permite a adição sequencial de grupos de componentes (R, L, C, RL, RC, RLC em Série ou Impedância Conhecida) e a conexão desses grupos (Série ou Paralelo) para formar um circuito principal.
* **Cálculo de Impedância:** Calcula a impedância equivalente total ($Z_{eq}$) do circuito na frequência base.
* **Análise de Potência:** Calcula as potências **Ativa (P)**, **Reativa (Q)**, **Aparente (S)** e o **Fator de Potência (FP)**.
* **Análise Fasorial:** Calcula e plota os fasores de tensão e corrente de *todos* os componentes do circuito (usando a função recursiva `_propagate_phasors`).
* **Diagrama de Bode:** Plota a resposta em frequência (Magnitude da Impedância em dB) para análise de filtros e ressonância.

## ⚙️ Arquitetura e Estrutura de Classes (Versão 1.0)

O código utiliza uma arquitetura orientada a objetos para modelar o circuito:

| Classe/Objeto | Descrição |
| :--- | :--- |
| `Component` (Base) | Classe base para elementos R, L, C e Z Conhecida. Implementa o método `calculate_impedance`. |
| `CircuitGroup` | Representa agrupamentos de componentes (ou outros grupos) em **Série** ou **Paralelo**. Implementa a regra de combinação de impedâncias. |
| `CalculadoraCircuitosPorGrupo` | A classe principal que gerencia a GUI (Tkinter), a lógica de entrada de dados e a visualização dos resultados/gráficos (Matplotlib). |
| **Lógica Fasorial** | O módulo utiliza a biblioteca **`cmath`** (Python) para lidar com operações complexas, representando os fasores elétricos. |

## 🚀 Como Executar o Projeto

### Pré-requisitos
Você precisará do **Python 3.x** e das seguintes bibliotecas:

```bash
pip install numpy matplotlib

(O tkinter geralmente já vem instalado com a distribuição padrão do Python).

Passos de Execução
1- Clone o repositório (após o seu git push ser bem-sucedido):

*bash*:git clone [https://github.com/otoniel-star/simulador-de-circuito-em-python.git](https://github.com/otoniel-star/simulador-de-circuito-em-python.git)
cd simulador-de-circuito-em-python

2- Execute o script principal:
python "import tkinter as tk.py"

Nota: Se o nome do arquivo foi corrigido localmente para main.py ou simulador.py, use o nome correto.
📈 Exemplo de UsoDefina a Tensão da Fonte (V_rms) e a Frequência Base (f).Crie um grupo, por exemplo, um "RL (Série)" com $R = 10 \Omega$ e $L = 0.1 H$.Clique em "Calcular Impedância do Grupo".Clique em "Adicionar em Série" (ou Paralelo) para adicionar ao circuito principal.Repita os passos 2-4 para adicionar mais elementos.Clique em "Plotar Diagrama Fasorial" para ver a relação de fase de todas as grandezas.
