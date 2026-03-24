import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Dict, Optional, Any

from core.pdf_logic import func_converter_imagem_para_pdf, func_converter_pdf_imagem, func_juntar_pdfs, func_comprimir_pdf
from gui.reorganizer import JanelaReorganizador
from gui.pdf_viewer import PopupPDF
from gui.components.progress import ModalProgresso
from utils.logger import logger


class JanelaPrincipal(tk.Tk):
    """
    Classe base da Tela Inicial. Implementa a injeção do State Management dos Documentos Virtuais,
    os botões utilitários de barra e subordina Modais Filhos.
    """
    def __init__(self) -> None:
        super().__init__()
        self.title("PDFLab")
        self.geometry("800x500")
        self.janela_flutuante: Optional[tk.Toplevel] = None

        quadro_ferramentas = tk.Frame(self, bd=1, relief=tk.RAISED)
        quadro_ferramentas.pack(side=tk.TOP, fill=tk.X)

        quadro_lista = ttk.Frame(self)
        quadro_lista.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        quadro_funcoes = ttk.Frame(self, relief=tk.RAISED)
        quadro_funcoes.pack(side=tk.TOP, fill=tk.X)

        opcoes_botoes = [
            {"texto": "Adicionar", "comando": self.selecionar_arquivos},
            {"texto": "Remover", "comando": self.remover_arquivo},
            {"texto": "Subir", "comando": self.mover_acima},
            {"texto": "Descer", "comando": self.mover_abaixo},
            {"texto": "Limpar Lista", "comando": self.limpar_lista},
            {"texto": "Visualizar arquivo", "comando": self.abrir_pdf_visualizador},
            {"texto": "Sobre", "comando": self.exibir_sobre},
        ]

        for config in opcoes_botoes:
            botoes_barra = ttk.Button(quadro_ferramentas, text=config["texto"], command=config["comando"], compound=tk.TOP)
            botoes_barra.pack(side=tk.LEFT, padx=5, pady=5)

        colunas_arvore = ("nome_arquivo", "caminho_arquivo")
        self.arvore_arquivos = ttk.Treeview(quadro_lista, columns=colunas_arvore, show="headings")
        self.arvore_arquivos.heading("nome_arquivo", text="Nome do Arquivo")
        self.arvore_arquivos.heading("caminho_arquivo", text="Pasta do Arquivo")
        self.arvore_arquivos.column("nome_arquivo", width=200)
        self.arvore_arquivos.column("caminho_arquivo", width=400)

        barra_rolagem = ttk.Scrollbar(quadro_lista, orient=tk.VERTICAL, command=self.arvore_arquivos.yview)
        self.arvore_arquivos.configure(yscrollcommand=barra_rolagem.set)

        self.arvore_arquivos.grid(row=0, column=0, sticky="nsew")
        barra_rolagem.grid(row=0, column=1, sticky="ns")
        self.arvore_arquivos.bind("<Double-1>", self.evento_clique_duplo_arvore)
        self.arvore_arquivos.bind("<Button-1>", self.evento_clique_arvore)
        self.arvore_arquivos.bind("<<TreeviewSelect>>", self.evento_selecao_arvore)
        
        quadro_lista.grid_rowconfigure(0, weight=1)
        quadro_lista.grid_columnconfigure(0, weight=1)

        self.arquivos_mapeados: List[str] = []
        self.documentos_virtuais: Dict[str, bytes] = {}

        funcoes_adicionais = [
            {"texto": "Juntar arquivos", "comando": self.juntar_arquivos},
            {"texto": "Comprimir arquivo", "comando": self.comprimir_arquivos},
            {"texto": "Organizar arquivo", "comando": self.organizar_arquivo},
            {"texto": "Converter em imagem", "comando": self.converter_arquivos_imagem},
            {"texto": "Salvar Alterações", "comando": self.salvar_alteracoes}
        ]

        self.botao_salvar_alteracoes: Optional[ttk.Button] = None
        for conf_funcional in funcoes_adicionais:
            botao_funcional = ttk.Button(quadro_funcoes, text=conf_funcional["texto"], command=conf_funcional["comando"], compound=tk.TOP)
            botao_funcional.pack(side=tk.LEFT, padx=5, pady=5)
            if conf_funcional["texto"] == "Salvar Alterações":
                self.botao_salvar_alteracoes = botao_funcional
                self.botao_salvar_alteracoes.config(state="disabled")

    def selecionar_arquivos(self) -> None:
        caminhos = filedialog.askopenfilenames(
            title="Selecione os arquivos.",
            filetypes=(("Arquivos suportados", ["*.jpg", "*.jpeg", "*.png", "*.pdf"]), ("Todos os arquivos", "*.*"))
        )
        for arquivo in caminhos:
            if arquivo not in self.arquivos_mapeados:
                self.arquivos_mapeados.append(arquivo)
        self.atualizar_arvore_arquivos()

    def remover_arquivo(self) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        if not itens_selecionados: return
        for item in itens_selecionados:
            indice = self.arvore_arquivos.index(item)
            caminho = self.arquivos_mapeados.pop(indice)
            if caminho in self.documentos_virtuais:
                del self.documentos_virtuais[caminho]
            self.arvore_arquivos.delete(item)

    def mover_acima(self) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        if not itens_selecionados: return
        indices = sorted([self.arvore_arquivos.index(i) for i in itens_selecionados])
        if indices[0] == 0: return

        lista_novos_indices = []
        for indice in indices:
            dados_item = self.arquivos_mapeados.pop(indice)
            self.arquivos_mapeados.insert(indice - 1, dados_item)
            nova_id_item = self.arvore_arquivos.get_children()[indice - 1]
            lista_novos_indices.append(nova_id_item)

        novos_indices = sorted([self.arvore_arquivos.index(i) for i in lista_novos_indices])
        self.atualizar_arvore_arquivos()
        for selecao in novos_indices:
            self.arvore_arquivos.selection_add(self.arvore_arquivos.get_children()[selecao])

    def mover_abaixo(self) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        if not itens_selecionados: return
        indices = sorted([self.arvore_arquivos.index(i) for i in itens_selecionados])
        if indices[-1] == len(self.arquivos_mapeados) - 1: return

        lista_novos_indices = []
        for indice in reversed(indices):
            dados_item = self.arquivos_mapeados.pop(indice)
            self.arquivos_mapeados.insert(indice + 1, dados_item)
            nova_id_item = self.arvore_arquivos.get_children()[indice + 1]
            lista_novos_indices.append(nova_id_item)

        novos_indices = sorted([self.arvore_arquivos.index(i) for i in lista_novos_indices])
        self.atualizar_arvore_arquivos()
        for selecao in novos_indices:
            self.arvore_arquivos.selection_add(self.arvore_arquivos.get_children()[selecao])

    def limpar_lista(self) -> None:
        for item in self.arvore_arquivos.get_children():
            self.arvore_arquivos.delete(item)
        self.arquivos_mapeados.clear()
        self.documentos_virtuais.clear()

    def exibir_sobre(self) -> None:
        texto_sobre = (
            "PDFLab - Processamento Inteligente de Documentos\n"
            "Versão 2.4.0 (Build Refatorada)\n\n"
            "Desenvolvido sob medida para facilitar e automatizar fluxos de\n"
            "trabalho intensos com arquivos PDF, prezando por performance e UX.\n\n"
            "Recursos Principais Integrados (V2):\n"
            " • Reorganizador Dinâmico In-Memory com Caching\n"
            " • Viewport Rápida: Recortes, Rotações e Redimensão\n"
            " • Compressor de Padrão Otimizado de Limite de Megabytes\n"
            " • Exportador Nativo de Arquivos em PNG/Imagem\n"
            " • Motor de Sincronia de Filas para Salvamento em Massa Seguro\n\n"
            "© 2026. Todos os direitos reservados."
        )
        messagebox.showinfo("Sobre o PDFLab", texto_sobre)

    def atualizar_arvore_arquivos(self) -> None:
        for item in self.arvore_arquivos.get_children():
            self.arvore_arquivos.delete(item)
        for arquivo in self.arquivos_mapeados:
            pasta, nome_arquivo = os.path.split(arquivo)
            self.arvore_arquivos.insert("", tk.END, text=nome_arquivo, values=[nome_arquivo, pasta])

    def _thread_juntar(self, arquivos_mapeados: List[str], caminho_saida: str, mapa_conversoes: Dict[str, bytes], rastreio_virtual: Dict[str, bytes], fila: Any) -> None:
        try:
            fila.put({"tipo": "iniciando_arquivo", "total": 1, "atual": 0, "arquivo": "Preparando compilação (Analizando páginas...)"})
            func_juntar_pdfs(arquivos_mapeados, caminho_saida, mapa_conversoes, rastreio_virtual, fila=fila)
            self.after(0, self._adicionar_arquivo_na_memoria, caminho_saida)
            fila.put({"tipo": "progresso", "atual": 1})
            fila.put({"tipo": "sucesso"})
        except Exception as erro_thread:
            logger.error(f"Erro crasso na Função Mesclar em background: {erro_thread}")
            fila.put({"tipo": "erro", "mensagem": str(erro_thread)})

    def juntar_arquivos(self) -> None:
        if len(self.arquivos_mapeados) <= 1:
            self.selecionar_arquivos()
            return

        mapa_conversoes = {}
        for arquivo in self.arquivos_mapeados:
            if os.path.splitext(arquivo)[1].lower() in [".png", ".jpg", ".jpeg"]:
                logger.info(f"Pré-convertendo imagem dinamicamente para Mesclagem Final: {arquivo}")
                origem_imagem = self.documentos_virtuais.get(arquivo, arquivo)
                mapa_conversoes[arquivo] = func_converter_imagem_para_pdf(origem_imagem, stream=True)

        caminho_saida = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=(("Arquivos PDF", "*.pdf"),), title="Salvar compilação PDF como..."
        )
        if not caminho_saida: return

        ModalProgresso(
            pai=self,
            titulo="Mesclando Fragmentos e Analisando Compressão...",
            funcao_alvo=self._thread_juntar,
            argumentos_funcao=(self.arquivos_mapeados, caminho_saida, mapa_conversoes, self.documentos_virtuais)
        )

    def _thread_compressao(self, caminhos: List[str], rastreio_virtual: Dict[str, bytes], fila: Any) -> None:
        try:
            import re
            from datetime import datetime
            total_arquivos = len(caminhos)
            sufixo = datetime.now().strftime("_%y%m%d_%H%M%S")
            padrao_sufixo = re.compile(r"_\d{6,8}_\d{6}$")
            
            for i, caminho in enumerate(caminhos):
                nome_base = Path(caminho).stem
                nome_base_limpo = padrao_sufixo.sub("", nome_base)
                if Path(caminho).suffix.lower() == ".pdf":
                    if total_arquivos > 1:
                        fila.put({"tipo": "iniciando_arquivo", "total": total_arquivos, "atual": i + 1, "arquivo": nome_base_limpo})
                    nova_nomenclatura = str(Path(caminho).with_name(f"{nome_base_limpo}_comprimido{sufixo}.pdf"))
                    func_comprimir_pdf(arquivo_entrada=caminho, arquivo_saida=nova_nomenclatura, documentos_virtuais=rastreio_virtual, fila=fila)
                    self.after(0, self._substituir_caminho_na_memoria, caminho, nova_nomenclatura)
                    if total_arquivos > 1:
                        fila.put({"tipo": "progresso", "atual": i + 1})
            fila.put({"tipo": "sucesso"})
        except Exception as erro_thread:
            fila.put({"tipo": "erro", "mensagem": str(erro_thread)})

    def comprimir_arquivos(self) -> None:
        if not self.arquivos_mapeados:
            self.selecionar_arquivos()
            return
            
        ModalProgresso(
            pai=self,
            titulo="Diminuindo Escala Mestra (Compressão PDF)...",
            funcao_alvo=self._thread_compressao,
            argumentos_funcao=(self.arquivos_mapeados, self.documentos_virtuais)
        )

    def abrir_pdf_visualizador(self) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        if not self.arquivos_mapeados:
            self.selecionar_arquivos()
            return
        if not itens_selecionados: return
        
        indices = sorted([self.arvore_arquivos.index(i) for i in itens_selecionados])
        caminho_alvo = self.arquivos_mapeados[indices[0]]

        if self.janela_flutuante and self.janela_flutuante.winfo_exists():
            self.janela_flutuante.on_close()

        self.janela_flutuante = PopupPDF(self, caminho_alvo)
        self.janela_flutuante.grab_set()
        self.janela_flutuante.bind("<Destroy>", self._verificar_estado_botoes, add="+")

    def _verificar_estado_botoes(self, evento: tk.Event) -> None:
        if self.janela_flutuante and evento.widget == self.janela_flutuante:
            self.evento_selecao_arvore(None)

    def evento_clique_duplo_arvore(self, evento: tk.Event) -> None:
        id_elemento = self.arvore_arquivos.identify_row(evento.y)
        if not id_elemento: return

        indice_clicado = self.arvore_arquivos.index(id_elemento)
        caminho_alvo = self.arquivos_mapeados[indice_clicado]

        if self.janela_flutuante and self.janela_flutuante.winfo_exists():
            self.janela_flutuante.on_close()

        self.janela_flutuante = PopupPDF(self, caminho_alvo)
        self.janela_flutuante.grab_set()
        self.janela_flutuante.bind("<Destroy>", self._verificar_estado_botoes, add="+")

    def organizar_arquivo(self) -> None:
        """Invoca a janela de paginação e edição sub-matriz."""
        if not self.arquivos_mapeados:
            caminho_alvo = filedialog.askopenfilename(title="Selecione Base PDF", filetypes=[("PDF", "*.pdf")])
        elif self.arvore_arquivos.selection():
            indice_selecao = self.arvore_arquivos.index(self.arvore_arquivos.selection()[0])
            caminho_alvo = self.arquivos_mapeados[indice_selecao]
        else:
            caminho_alvo = next((arq for arq in self.arquivos_mapeados if arq.lower().endswith(".pdf")), None)
            
        if not caminho_alvo or not caminho_alvo.lower().endswith(".pdf"): return

        if self.janela_flutuante and self.janela_flutuante.winfo_exists():
            self.janela_flutuante.on_close()
            
        self.janela_flutuante = JanelaReorganizador(self, caminho_alvo)
        self.janela_flutuante.grab_set()
        self.janela_flutuante.bind("<Destroy>", self._verificar_estado_botoes, add="+")

    def _thread_conversao(self, caminhos: List[str], rastreio_virtual: Dict[str, bytes], fila: Any) -> None:
        try:
            total_arquivos = len(caminhos)
            for i, caminho in enumerate(caminhos):
                nome_base = Path(caminho).stem
                fila.put({"tipo": "iniciando_arquivo", "total": total_arquivos, "atual": i + 1, "arquivo": nome_base})
                func_converter_pdf_imagem(caminho_pdf=caminho, documentos_virtuais=rastreio_virtual)
                fila.put({"tipo": "progresso", "atual": i + 1})
            fila.put({"tipo": "sucesso"})
        except Exception as erro_thread:
            fila.put({"tipo": "erro", "mensagem": str(erro_thread)})

    def converter_arquivos_imagem(self) -> None:
        """Inicia um Modal de Progresso injetando a thread limitante de OOM (Out Of Memory)."""
        if not self.arquivos_mapeados:
            caminhos_extensivos = filedialog.askopenfilenames(title="Selecione Conjunto PDF", filetypes=[("PDF", "*.pdf")])
            for arq in caminhos_extensivos:
                if arq not in self.arquivos_mapeados: self.arquivos_mapeados.append(arq)
            self.atualizar_arvore_arquivos()
            caminhos_alvo = list(caminhos_extensivos)
        elif self.arvore_arquivos.selection():
            caminhos_alvo = [self.arquivos_mapeados[self.arvore_arquivos.index(elemento)] for elemento in self.arvore_arquivos.selection()]
        else:
            caminhos_alvo = [arq for arq in self.arquivos_mapeados if arq.lower().endswith(".pdf")]
            
        if not caminhos_alvo: return
        ModalProgresso(
            pai=self,
            titulo="Transmutando Matrizes PDF para PNG...",
            funcao_alvo=self._thread_conversao,
            argumentos_funcao=(caminhos_alvo, self.documentos_virtuais)
        )

    def evento_clique_arvore(self, evento: tk.Event) -> None:
        codigo_elemento = self.arvore_arquivos.identify_row(evento.y)
        if not codigo_elemento:
            self.arvore_arquivos.selection_set("")
            self.evento_selecao_arvore(None)

    def evento_selecao_arvore(self, evento: Optional[tk.Event]) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        habilitar = False
        for item in itens_selecionados:
            indice = self.arvore_arquivos.index(item)
            caminho = self.arquivos_mapeados[indice]
            if caminho in self.documentos_virtuais:
                habilitar = True
                break
        if getattr(self, "botao_salvar_alteracoes", None):
            self.botao_salvar_alteracoes.config(state="normal" if habilitar else "disabled")

    def salvar_alteracoes(self) -> None:
        itens_selecionados = self.arvore_arquivos.selection()
        arquivos_para_salvar = []
        for item in itens_selecionados:
            indice = self.arvore_arquivos.index(item)
            caminho = self.arquivos_mapeados[indice]
            if caminho in self.documentos_virtuais:
                arquivos_para_salvar.append(caminho)
        
        if not arquivos_para_salvar: return

        ModalProgresso(
            pai=self,
            titulo="Salvando Arquivos Editados...",
            funcao_alvo=self._thread_salvar_lote,
            argumentos_funcao=(arquivos_para_salvar, self.documentos_virtuais)
        )

    def _thread_salvar_lote(self, caminhos: List[str], rastreio_virtual: Dict[str, bytes], fila: Any) -> None:
        try:
            import re
            from datetime import datetime
            total = len(caminhos)
            sufixo = datetime.now().strftime("_%y%m%d_%H%M%S")
            padrao_sufixo = re.compile(r"_\d{6,8}_\d{6}$")
            
            for i, caminho in enumerate(caminhos):
                nome_base = Path(caminho).stem
                nome_base_limpo = padrao_sufixo.sub("", nome_base)
                extensao = Path(caminho).suffix
                fila.put({"tipo": "iniciando_arquivo", "total": total, "atual": i + 1, "arquivo": f"Salvando {nome_base_limpo}..."})
                novo_caminho = str(Path(caminho).with_name(f"{nome_base_limpo}{sufixo}{extensao}"))
                
                with open(novo_caminho, "wb") as f:
                    f.write(rastreio_virtual[caminho])
                
                self.after(0, self._substituir_caminho_na_memoria, caminho, novo_caminho)
                fila.put({"tipo": "progresso", "atual": i + 1})
            
            fila.put({"tipo": "sucesso"})
        except Exception as erro_thread:
            fila.put({"tipo": "erro", "mensagem": str(erro_thread)})

    def _substituir_caminho_na_memoria(self, caminho_antigo: str, caminho_novo: str) -> None:
        if caminho_antigo in self.arquivos_mapeados:
            indice = self.arquivos_mapeados.index(caminho_antigo)
            self.arquivos_mapeados[indice] = caminho_novo
            
            if caminho_antigo in self.documentos_virtuais:
                del self.documentos_virtuais[caminho_antigo]
                
            self.atualizar_arvore_arquivos()
            item_id = self.arvore_arquivos.get_children()[indice]
            self.arvore_arquivos.selection_add(item_id)
            self.evento_selecao_arvore(None)

    def _adicionar_arquivo_na_memoria(self, caminho_novo: str) -> None:
        if caminho_novo not in self.arquivos_mapeados:
            self.arquivos_mapeados.append(caminho_novo)
            self.atualizar_arvore_arquivos()
            indice = len(self.arquivos_mapeados) - 1
            item_id = self.arvore_arquivos.get_children()[indice]
            self.arvore_arquivos.selection_add(item_id)
            self.evento_selecao_arvore(None)
