import os
import io
import concurrent.futures
import threading
import tkinter as tk
from tkinter import Button, Canvas, Frame, Label, Scrollbar, StringVar, Toplevel, simpledialog, ttk
from tkinter.filedialog import asksaveasfilename
from tkinter.messagebox import showinfo
from typing import List, Optional, Any, Dict

import pymupdf
from PIL import Image, ImageTk

from gui.components.progress import ModalProgresso
from utils.logger import logger

LARGURA_MINIATURA = 120
ALTURA_MINIATURA = int(LARGURA_MINIATURA * (297 / 210))  # Proporção A4
COR_FUNDO = "#333333"
COR_FUNDO_MINIATURA = "#444444"
COR_SELECAO = "#0078D7"
COLUNAS_GRADE = 5


class JanelaReorganizador(Toplevel):
    def __init__(self, pai: tk.Tk, caminho_pdf: str) -> None:
        super().__init__(pai)
        self.title("Reorganizar Páginas do PDF")
        self.geometry("710x796")

        self.caminho_pdf = caminho_pdf
        
        try:
            if self.caminho_pdf in pai.documentos_virtuais:
                self.bytes_pdf = pai.documentos_virtuais[self.caminho_pdf]
            else:
                with open(caminho_pdf, "rb") as arquivo_fisico:
                    self.bytes_pdf = arquivo_fisico.read()
            self.documento = pymupdf.open(stream=self.bytes_pdf, filetype="pdf")
            self.ordem_paginas: List[int] = list(range(self.documento.page_count))
            self.ordem_paginas_original: List[int] = list(self.ordem_paginas)
            self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        except Exception as erro_abertura:
            logger.error(f"Erro Fatal ao Abrir Documento Reorganizer: {erro_abertura}")
            showinfo("Erro Crítico", f"Falha na abertura via motor de PDF\n\n{erro_abertura}", parent=self)
            self.destroy()
            return
            
        self.posicoes_selecionadas: List[int] = []
        self.ultima_posicao_clicada: Optional[int] = None
        self.houve_edicao = False
        self.widgets_miniaturas: List[Frame] = []
        self.imagens_pil: List[Optional[Image.Image]] = []
        self.imagens_tk: List[ImageTk.PhotoImage] = []

        self.opcao_exportacao = StringVar(value="selected_only")

        self._configurar_interface()

        self.rotulo_carregando.pack(pady=20)
        ModalProgresso(
            pai=self,
            titulo="Gerando Grades Espaciais...",
            funcao_alvo=self._thread_gerar_miniaturas,
            argumentos_funcao=()
        )

    def _configurar_interface(self) -> None:
        quadro_lona = Frame(self)
        quadro_lona.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.lona = Canvas(quadro_lona, highlightthickness=0)
        barra_rolagem = Scrollbar(quadro_lona, orient=tk.VERTICAL, command=self.lona.yview)
        self.lona.configure(yscrollcommand=barra_rolagem.set)
        
        barra_rolagem.pack(side=tk.RIGHT, fill=tk.Y)
        self.lona.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.conteiner_miniaturas = Frame(self.lona)

        self.item_janela_lona = self.lona.create_window((0, 0), window=self.conteiner_miniaturas, anchor="ne")

        self.conteiner_miniaturas.bind("<Configure>", self._ao_configurar_quadro)
        self.lona.bind("<Configure>", self._centralizar_quadro_na_lona)

        # Controles
        quadro_controles = Frame(self)
        quadro_controles.pack(fill=tk.X, pady=5)
        
        self.botao_inicio = Button(quadro_controles, text="↑↑ Início", command=lambda: self._mover_selecao("start"), state="disabled")
        self.botao_cima = Button(quadro_controles, text="↑ Cima", command=lambda: self._mover_selecao("up"), state="disabled")
        self.botao_baixo = Button(quadro_controles, text="↓ Baixo", command=lambda: self._mover_selecao("down"), state="disabled")
        self.botao_fim = Button(quadro_controles, text="↓↓ Fim", command=lambda: self._mover_selecao("end"), state="disabled")
        self.botao_mover_para = Button(quadro_controles, text="Mover Para...", command=self._mover_selecao_para_posicao, state="disabled")

        self.botao_girar_anti_horario = Button(quadro_controles, text="Girar ↺", command=lambda: self._rotacionar_selecao(90), state="disabled", bg="#17A2B8", fg="white")
        self.botao_girar_horario = Button(quadro_controles, text="Girar ↻", command=lambda: self._rotacionar_selecao(-90), state="disabled", bg="#17A2B8", fg="white")

        self.botao_mover_para.pack(side=tk.LEFT, padx=10, expand=True)
        self.botao_girar_anti_horario.pack(side=tk.LEFT, padx=5, expand=True)
        self.botao_girar_horario.pack(side=tk.LEFT, padx=5, expand=True)
        self.botao_inicio.pack(side=tk.LEFT, padx=5, expand=True)
        self.botao_cima.pack(side=tk.LEFT, padx=5, expand=True)
        self.botao_baixo.pack(side=tk.LEFT, padx=5, expand=True)
        self.botao_fim.pack(side=tk.LEFT, padx=5, expand=True)

        self.quadro_rotulo_exportacao = ttk.Labelframe(self, text=" Exportar a Partir da Seleção ")
        self.quadro_rotulo_exportacao.pack(fill="x", padx=10, pady=5)

        quadro_radio_exportacao = Frame(self.quadro_rotulo_exportacao)
        quadro_radio_exportacao.pack(side="left", padx=10, pady=5, expand=True)

        self.radio_apenas_selecionados = ttk.Radiobutton(quadro_radio_exportacao, text="Salvar APENAS as páginas selecionadas", variable=self.opcao_exportacao, value="selected_only")
        self.radio_apenas_selecionados.pack(anchor="w")

        self.radio_excluir_selecionados = ttk.Radiobutton(quadro_radio_exportacao, text="Salvar TUDO, EXCETO as páginas selecionadas", variable=self.opcao_exportacao, value="exclude_selected")
        self.radio_excluir_selecionados.pack(anchor="w")

        self.botao_executar_exportacao = Button(self.quadro_rotulo_exportacao, text="Exportar...", command=self._executar_exportacao, bg="#17A2B8", fg="white")
        self.botao_executar_exportacao.pack(side="right", padx=10, pady=5)

        quadro_acoes = Frame(self)
        quadro_acoes.pack(fill=tk.X, pady=10)

        Button(quadro_acoes, text="Salvar como um Novo Arquivo...", command=self._aplicar_e_salvar_novo).pack(side=tk.RIGHT, padx=10)
        Button(quadro_acoes, text="Aplicar e Fechar", command=self._ao_fechar, bg="#28a745", fg="white").pack(side=tk.RIGHT, padx=5)
        Button(quadro_acoes, text="Descartar Alterações", command=self._redefinir_ordem_original).pack(side=tk.RIGHT, padx=5)
        Button(quadro_acoes, text="Cancelar (Sair sem Salvar)", command=self._cancelar_e_fechar).pack(side=tk.RIGHT)

        self.rotulo_carregando = Label(self.conteiner_miniaturas, text="Carregando miniaturas...", font=("Arial", 16))
        self.bind_all("<MouseWheel>", self._ao_rolar_mouse)

        self._atualizar_estados_botoes()

    def _centralizar_quadro_na_lona(self, evento: tk.Event) -> None:
        largura_lona = evento.width
        self.lona.coords(self.item_janela_lona, largura_lona // 2, 0)

    def _atualizar_estados_botoes(self) -> None:
        estado_movimento = "normal" if self.posicoes_selecionadas else "disabled"

        self.botao_inicio.config(state=estado_movimento)
        self.botao_cima.config(state=estado_movimento)
        self.botao_baixo.config(state=estado_movimento)
        self.botao_fim.config(state=estado_movimento)
        self.botao_mover_para.config(state=estado_movimento)
        self.botao_girar_anti_horario.config(state=estado_movimento)
        self.botao_girar_horario.config(state=estado_movimento)

        for widget in self.quadro_rotulo_exportacao.winfo_children():
            if isinstance(widget, Frame):
                for sub_widget in widget.winfo_children():
                    sub_widget.configure(state=estado_movimento)
            else:
                widget.configure(state=estado_movimento)

        if 0 in self.posicoes_selecionadas:
            self.botao_inicio.config(state="disabled")
            self.botao_cima.config(state="disabled")
            
        if len(self.ordem_paginas) - 1 in self.posicoes_selecionadas:
            self.botao_baixo.config(state="disabled")
            self.botao_fim.config(state="disabled")

    def _aplicar_e_salvar_novo(self) -> None:
        caminho_salvamento = asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Arquivos PDF", "*.pdf")],
            title="Salvar PDF Reorganizado",
            initialfile=f"{os.path.splitext(os.path.basename(self.caminho_pdf))[0]}_reorganizado.pdf",
        )
        if not caminho_salvamento: return

        try:
            logger.info(f"Salvando reorganização externa em : {caminho_salvamento}")
            copia_documento = pymupdf.open(stream=self.bytes_pdf, filetype="pdf")
            copia_documento.select(self.ordem_paginas)
            copia_documento.save(caminho_salvamento, garbage=4, deflate=True)
            copia_documento.close()
            showinfo("Sucesso", f"O arquivo foi salvo com sucesso em:\n{caminho_salvamento}", parent=self)
        except Exception as erro_salvamento:
            logger.error(f"Erro em reorganização externa: {erro_salvamento}")
            showinfo("Erro", f"Ocorreu um erro ao salvar o arquivo:\n{erro_salvamento}", parent=self)

    def _executar_exportacao(self) -> None:
        modo_exportacao = self.opcao_exportacao.get()

        caminho_salvamento = asksaveasfilename(
            defaultextension=".pdf", filetypes=[("Arquivos PDF", "*.pdf")],
            title="Exportar Páginas Selecionadas",
            initialfile=f"{os.path.splitext(os.path.basename(self.caminho_pdf))[0]}_exportado.pdf",
        )
        if not caminho_salvamento: return

        paginas_manter = []
        if modo_exportacao == "selected_only":
            posicoes_ordenadas = sorted(self.posicoes_selecionadas)
            paginas_manter = [self.ordem_paginas[pos] for pos in posicoes_ordenadas]
        elif modo_exportacao == "exclude_selected":
            indices_excluir = {self.ordem_paginas[pos] for pos in self.posicoes_selecionadas}
            paginas_manter = [indice_pag for indice_pag in self.ordem_paginas if indice_pag not in indices_excluir]

        if not paginas_manter:
            showinfo("Aviso", "A seleção resultou em um PDF sem páginas. A operação foi cancelada.", parent=self)
            return

        try:
            logger.info(f"Exportando subset de arquivo: {caminho_salvamento} (Modo: {modo_exportacao})")
            copia_documento = pymupdf.open(stream=self.bytes_pdf, filetype="pdf")
            copia_documento.select(paginas_manter)
            copia_documento.save(caminho_salvamento, garbage=4, deflate=True)
            copia_documento.close()
            showinfo("Sucesso", f"O arquivo foi exportado com sucesso em:\n{caminho_salvamento}", parent=self)
        except Exception as erro_exportacao:
            logger.error(f"Erro na exportação subset: {erro_exportacao}")
            showinfo("Erro", f"Ocorreu um erro ao exportar o arquivo:\n{erro_exportacao}", parent=self)

    def _ao_configurar_quadro(self, evento: Any = None) -> None:
        self.lona.configure(scrollregion=self.lona.bbox("all"))

    def _ao_rolar_mouse(self, evento: tk.Event) -> None:
        self.lona.yview_scroll(int(-1 * (evento.delta / 120)), "units")

    def _criar_imagem_para_pagina(self, indice_pagina: int, bytes_documento: bytes) -> Image.Image:
        with pymupdf.open(stream=bytes_documento, filetype="pdf") as documento_interno:
            pagina_interna = documento_interno.load_page(indice_pagina)
            return self._criar_miniatura_preenchida(pagina_interna)

    def _thread_gerar_miniaturas(self, fila: Any) -> None:
        try:
            total_pag = self.documento.page_count
            self.imagens_pil = [None] * total_pag
            fila.put({"tipo": "iniciando_arquivo", "total": total_pag, "atual": 0, "arquivo": "Extraindo imagens da memória RAM..."})
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futuros = {executor.submit(self._criar_imagem_para_pagina, i, self.bytes_pdf): i for i in range(total_pag)}
                
                concluidos = 0
                for futuro in concurrent.futures.as_completed(futuros):
                    i = futuros[futuro]
                    self.imagens_pil[i] = futuro.result()
                    concluidos += 1
                    fila.put({"tipo": "progresso", "atual": concluidos})
                    
            fila.put({"tipo": "sucesso"})
            self.after(0, self._desenhar_grade)
        except Exception as erro_geracao:
            logger.error(f"Geração de Miniaturas (Thumbnail) falhou criticamente: {erro_geracao}")
            fila.put({"tipo": "erro", "mensagem": str(erro_geracao)})

    def _criar_miniatura_preenchida(self, pagina: pymupdf.Page, dpi: int = 72) -> Image.Image:
        matriz_img = pymupdf.Matrix(dpi / 72, dpi / 72)
        pixmap = pagina.get_pixmap(matrix=matriz_img)
        imagem_pil = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        imagem_pil.thumbnail((LARGURA_MINIATURA, ALTURA_MINIATURA), Image.Resampling.LANCZOS)
        imagem_preenchida = Image.new("RGB", (LARGURA_MINIATURA, ALTURA_MINIATURA), COR_FUNDO_MINIATURA)
        posicao_colagem = (
            (LARGURA_MINIATURA - imagem_pil.width) // 2,
            (ALTURA_MINIATURA - imagem_pil.height) // 2,
        )
        imagem_preenchida.paste(imagem_pil, posicao_colagem)
        return imagem_preenchida

    def _desenhar_grade(self) -> None:
        self.rotulo_carregando.destroy()
        for widget in self.conteiner_miniaturas.winfo_children():
            widget.destroy()
        self.imagens_tk.clear()
        self.widgets_miniaturas.clear()
        
        for posicao, indice_pagina_original in enumerate(self.ordem_paginas):
            imagem_pil_cache = self.imagens_pil[indice_pagina_original]
            if imagem_pil_cache:
                imagem_tk = ImageTk.PhotoImage(imagem_pil_cache)
                self.imagens_tk.append(imagem_tk)
                
                quadro_miniatura = Frame(self.conteiner_miniaturas, bg=COR_FUNDO_MINIATURA, cursor="hand2")
                rotulo_imagem = Label(quadro_miniatura, image=imagem_tk, bg=COR_FUNDO_MINIATURA)
                rotulo_imagem.pack()
                
                rotulo_numero = Label(quadro_miniatura, text=f"Pág. {indice_pagina_original + 1}", bg=COR_FUNDO_MINIATURA, fg="white")
                rotulo_numero.pack(pady=2)
                
                for elemento_visual in [quadro_miniatura, rotulo_imagem, rotulo_numero]:
                    elemento_visual.bind("<Button-1>", lambda evento, pos=posicao: self._ao_clicar_miniatura(evento, pos))
                    elemento_visual.bind("<Double-Button-1>", lambda evento, idx_orig=indice_pagina_original: self._exibir_preview_pagina(idx_orig))
                    
                linha, coluna = divmod(posicao, COLUNAS_GRADE)
                quadro_miniatura.grid(row=linha, column=coluna, padx=5, pady=5)
                self.widgets_miniaturas.append(quadro_miniatura)
            
        if self.posicoes_selecionadas:
            self._atualizar_visual_selecao()

    def _ao_clicar_miniatura(self, evento: tk.Event, posicao: int) -> None:
        if evento.state & 1 and self.ultima_posicao_clicada is not None:
            inicio, fim = min(self.ultima_posicao_clicada, posicao), max(self.ultima_posicao_clicada, posicao)
            self.posicoes_selecionadas = list(range(inicio, fim + 1))
        elif evento.state & 4:
            if posicao in self.posicoes_selecionadas:
                self.posicoes_selecionadas.remove(posicao)
            else:
                self.posicoes_selecionadas.append(posicao)
            self.ultima_posicao_clicada = posicao
        else:
            self.posicoes_selecionadas = [posicao]
            self.ultima_posicao_clicada = posicao
            
        self._atualizar_visual_selecao()
        self._atualizar_estados_botoes()

    def _atualizar_visual_selecao(self) -> None:
        for indice, widget in enumerate(self.widgets_miniaturas):
            cor_alvo = COR_SELECAO if indice in self.posicoes_selecionadas else COR_FUNDO_MINIATURA
            for elemento_filho in widget.winfo_children():
                elemento_filho.configure(bg=cor_alvo)
            widget.configure(bg=cor_alvo)

    def _mover_selecao(self, direcao: str) -> None:
        if not self.posicoes_selecionadas: return
        posicoes_mover = sorted(self.posicoes_selecionadas)
        paginas_mover = [self.ordem_paginas[p] for p in posicoes_mover]
        for pos in reversed(posicoes_mover):
            self.ordem_paginas.pop(pos)
            
        if direcao == "up":
            nova_pos_insercao = max(0, posicoes_mover[0] - 1)
        elif direcao == "down":
            nova_pos_insercao = min(len(self.ordem_paginas), posicoes_mover[0] + 1)
        elif direcao == "start":
            nova_pos_insercao = 0
        elif direcao == "end":
            nova_pos_insercao = len(self.ordem_paginas)
        else:
            return
            
        for i, pagina in enumerate(paginas_mover):
            self.ordem_paginas.insert(nova_pos_insercao + i, pagina)
            
        self.posicoes_selecionadas = list(range(nova_pos_insercao, nova_pos_insercao + len(paginas_mover)))
        self.ultima_posicao_clicada = self.posicoes_selecionadas[-1]
        self._desenhar_grade()
        self._atualizar_estados_botoes()

    def _exibir_preview_pagina(self, indice_pagina_original: int) -> None:
        from gui.pdf_viewer import PopupPDF
        import io
        
        if getattr(self, "houve_edicao", False) and self.documento:
            buffer_saida = io.BytesIO()
            self.documento.save(buffer_saida, garbage=4, deflate=True)
            self.master.documentos_virtuais[self.caminho_pdf] = buffer_saida.getvalue()
            self.bytes_pdf = self.master.documentos_virtuais[self.caminho_pdf]
            self.houve_edicao = False
        
        if hasattr(self, "janela_preview") and self.janela_preview and self.janela_preview.winfo_exists():
            if hasattr(self.janela_preview, "ao_fechar"):
                self.janela_preview.ao_fechar()
            else:
                self.janela_preview.destroy()
            
        self.janela_preview = PopupPDF(self, self.caminho_pdf, pagina_inicial=indice_pagina_original)
        self.janela_preview.bind("<Destroy>", self._ao_fechar_preview_externo, add="+")

    def _ao_fechar_preview_externo(self, evento: tk.Event) -> None:
        if hasattr(self, "janela_preview") and evento.widget == self.janela_preview:
            if getattr(self.janela_preview, "houve_edicao", False):
                if self.caminho_pdf in self.master.documentos_virtuais:
                    self.bytes_pdf = self.master.documentos_virtuais[self.caminho_pdf]
                    if self.documento and not getattr(self.documento, 'is_closed', False):
                        self.documento.close()
                    self.documento = pymupdf.open(stream=self.bytes_pdf, filetype="pdf")
                    
                    self.rotulo_carregando = Label(self, text="Recarregando miniaturas...", fg="white", bg=COR_FUNDO_MINIATURA, font=("Segoe UI", 12))
                    self.rotulo_carregando.pack(pady=20)
                    
                    from gui.components.progress import ModalProgresso
                    ModalProgresso(
                        pai=self,
                        titulo="Adquirindo edições da página...",
                        funcao_alvo=self._thread_gerar_miniaturas,
                        argumentos_funcao=()
                    )

    def _redefinir_ordem_original(self) -> None:
        self.ordem_paginas = self.ordem_paginas_original.copy()
        self.posicoes_selecionadas = []
        self.ultima_posicao_clicada = None
        self.houve_edicao = False
        if not getattr(self.documento, 'is_closed', False):
            self.documento.close()
        self.documento = pymupdf.open(stream=self.bytes_pdf, filetype="pdf")
        
        self.rotulo_carregando = Label(self, text="Recarregando originais...", fg="white", bg=COR_FUNDO_MINIATURA, font=("Segoe UI", 12))
        self.rotulo_carregando.pack(pady=20)
        from gui.components.progress import ModalProgresso
        ModalProgresso(
            pai=self,
            titulo="Descartando edições...",
            funcao_alvo=self._thread_gerar_miniaturas,
            argumentos_funcao=()
        )

    def _rotacionar_selecao(self, angulo: int) -> None:
        if not self.posicoes_selecionadas: return
        self.houve_edicao = True
        
        paginas_reais = [self.ordem_paginas[p] for p in self.posicoes_selecionadas]
        for num_pag in paginas_reais:
            pag = self.documento[num_pag]
            nova_rotacao = (pag.rotation - angulo + 360) % 360
            pag.set_rotation(nova_rotacao)
            self.imagens_pil[num_pag] = self._criar_miniatura_preenchida(pag)
            
        self._desenhar_grade()

    def _mover_selecao_para_posicao(self) -> None:
        if not self.posicoes_selecionadas: return
        posicao_alvo = simpledialog.askinteger(
            "Mover Para Posição",
            f"Digite a nova posição (1 a {self.documento.page_count}):",
            parent=self, minvalue=1, maxvalue=self.documento.page_count,
        )
        if posicao_alvo is None: return
        
        indice_alvo = posicao_alvo - 1
        posicoes_mover = sorted(self.posicoes_selecionadas)
        
        if indice_alvo in posicoes_mover:
            showinfo("Movimento Inválido", "Você não pode mover para uma posição que já está selecionada.", parent=self)
            return
            
        paginas_mover = [self.ordem_paginas[p] for p in posicoes_mover]
        for pos in reversed(posicoes_mover):
            self.ordem_paginas.pop(pos)
            
        ajuste = sum(1 for pos in posicoes_mover if pos < indice_alvo)
        nova_pos_insercao = indice_alvo - ajuste
        
        for i, pagina in enumerate(paginas_mover):
            self.ordem_paginas.insert(nova_pos_insercao + i, pagina)
            
        self.posicoes_selecionadas = list(range(nova_pos_insercao, nova_pos_insercao + len(paginas_mover)))
        self.ultima_posicao_clicada = self.posicoes_selecionadas[-1]
        self._desenhar_grade()
        self._atualizar_estados_botoes()

    def _ao_fechar(self) -> None:
        if self.ordem_paginas != self.ordem_paginas_original or self.houve_edicao:
            try:
                self.documento.select(self.ordem_paginas)
                buffer_saida = io.BytesIO()
                self.documento.save(buffer_saida, garbage=4, deflate=True)
                self.master.documentos_virtuais[self.caminho_pdf] = buffer_saida.getvalue()
                logger.info(f"Reorganização/edição salva em memória para: {self.caminho_pdf}")
            except Exception as erro_salvamento_virtual:
                logger.error(f"Erro ao persistir reorganização na memória: {erro_salvamento_virtual}")
        
        if not getattr(self.documento, 'is_closed', False):
            self.documento.close()
        self.destroy()

    def _cancelar_e_fechar(self) -> None:
        self.ordem_paginas = self.ordem_paginas_original.copy()
        self.destroy()
