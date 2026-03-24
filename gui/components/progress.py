import queue
import threading
import tkinter as tk
from tkinter import Toplevel, ttk, messagebox
from typing import Callable, Any, Tuple

from utils.logger import logger

class ModalProgresso(Toplevel):
    """
    Componente modular que:
    1. Cria uma janela modal bloqueante na interface gráfica.
    2. Inicia uma thread em background executando uma função de trabalho (worker).
    3. Monitora uma fila (queue) para atualizar constantemente a barra de progresso.
    """
    def __init__(self, pai: tk.Tk, titulo: str, funcao_alvo: Callable[..., Any], argumentos_funcao: Tuple[Any, ...]) -> None:
        super().__init__(pai)
        self.title(titulo)
        
        self.transient(pai)
        self.resizable(False, False)
        
        self.rotulo_status = ttk.Label(self, text="Inicializando processamento...", anchor="w", width=50)
        self.rotulo_status.pack(pady=(10, 5), padx=10, fill="x")

        self.barra_progresso = ttk.Progressbar(self, orient='horizontal', length=300, mode='determinate')
        self.barra_progresso.pack(pady=(0, 15), padx=10)

        # Centralização automática em relação à janela mestre
        self.update_idletasks()
        try:
            mestre_x = pai.winfo_x()
            mestre_y = pai.winfo_y()
            mestre_l = pai.winfo_width()
            mestre_a = pai.winfo_height()
            
            pos_x = mestre_x + (mestre_l // 2) - (self.winfo_width() // 2)
            pos_y = mestre_y + (mestre_a // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{pos_x}+{pos_y}")
        except Exception:
            pass # Ignora falhas de geometria silenciosamente
            
        self.focus_set()
        self.grab_set()

        self.fila_feedback = queue.Queue()
        
        # Como o worker precisa de uma fila para reportar progresso, passamos a nossa no final da Tupla
        argumentos_completos = list(argumentos_funcao)
        argumentos_completos.append(self.fila_feedback)
        
        self.thread_trabalho = threading.Thread(
            target=funcao_alvo,
            args=tuple(argumentos_completos),
            daemon=True
        )
        self.thread_trabalho.start()
        
        # Inicia listener de rotina cíclica para fiscalizar as métricas de término.
        self.after(100, self.processar_fila)

    def processar_fila(self) -> None:
        encerrar_laco = False
        mensagens_processadas = 0
        try:
            while not self.fila_feedback.empty() and mensagens_processadas < 30:
                mensagem = self.fila_feedback.get_nowait()
                mensagens_processadas += 1
                
                if mensagem["tipo"] == "iniciando_arquivo":
                    self.barra_progresso['maximum'] = mensagem['total']
                    self.barra_progresso['value'] = mensagem.get('atual', 0)
                    self.rotulo_status.config(text=f"Processando {mensagem['atual']}/{mensagem['total']}: {mensagem['arquivo']}")
                    
                elif mensagem["tipo"] == "progresso":
                    self.barra_progresso['value'] = mensagem['atual']
                    texto_atual = f"Processando {mensagem['atual']}/{self.barra_progresso['maximum']}..."
                    self.rotulo_status.config(text=texto_atual)
                    
                elif mensagem["tipo"] == "sucesso":
                    self.rotulo_status.config(text="Operação finalizada com sucesso!")
                    self.barra_progresso['value'] = self.barra_progresso['maximum']
                    # Atualiza UI antes de fechar
                    self.update_idletasks()
                    # Manter a janela aberta brevemente antes de fechar
                    encerrar_laco = True
                    self.after(800, self.destroy)  # fechar após 0.8 segundos

                    
                elif mensagem["tipo"] == "erro":
                    self.rotulo_status.config(text="Erro ao processar arquivo.")
                    logger.error(f"Erro mapeado em Thread secundária: {mensagem['mensagem']}")
                    messagebox.showerror("Erro Operacional", str(mensagem["mensagem"]), parent=self)
                    encerrar_laco = True
                    
        except queue.Empty:
            pass
        except Exception as erro:
            logger.error(f"Erro generalizado na leitura da Fila (Queue): {erro}")

        if mensagens_processadas > 0:
            self.update_idletasks()

        if encerrar_laco:
            self.after(500, self.destroy)
        else:
            self.after(50, self.processar_fila)
