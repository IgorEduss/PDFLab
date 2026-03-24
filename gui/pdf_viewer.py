import io
import math
import os
import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Any, Tuple

import pymupdf
from PIL import Image, ImageTk

from core.pdf_logic import func_converter_imagem_para_pdf
from utils.logger import logger


class PopupPDF(tk.Toplevel):
    def __init__(self, pai: tk.Misc, caminho_arquivo: str, pagina_inicial: int = 0) -> None:
        super().__init__(pai)
        self.title(f"Editor - {os.path.basename(caminho_arquivo)}")
        self.app_mestre = self._get_app_mestre(pai)

        # Configuração da geometria da janela
        relacao_tela_janela = 0.875
        relacao_janela_a4 = 1 / math.sqrt(2)
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        self.nova_altura = int(altura_tela * relacao_tela_janela)
        self.nova_largura = int(self.nova_altura * relacao_janela_a4)
        pos_x = (largura_tela // 2) - (self.nova_largura // 2)
        pos_y = (altura_tela // 2) - (self.nova_altura // 2)
        self.geometry(f"{self.nova_largura}x{self.nova_altura}+{pos_x}+{pos_y}")

        # Variáveis de estado
        self.caminho_arquivo = caminho_arquivo
        self.tipo_arquivo = "pdf" if caminho_arquivo.lower().endswith(".pdf") else "imagem"
        self.indice_pagina_atual = pagina_inicial
        self.rotacoes: Dict[int, int] = {}
        self.cortes_pagina_pdf: Dict[int, Image.Image] = {}
        self.imagem_alterada = False 
        self.houve_edicao = False
        self.coordenadas_corte_imagem: Dict[int, Tuple[int, int, int, int]] = {}

        # Variáveis para manipulação de imagem
        self.imagem_pil_atual: Optional[Image.Image] = None
        self.imagem_pil_original: Optional[Image.Image] = None
        self.imagem_tk_foto: Optional[ImageTk.PhotoImage] = None

        # Variáveis de corte
        self.esta_cortando = False
        self.inicio_corte_x = 0.0
        self.inicio_corte_y = 0.0
        self.id_retangulo_corte: Optional[int] = None
        self.fator_escala_exibicao = 1.0
        self.deslocamento_x_imagem = 0.0
        self.deslocamento_y_imagem = 0.0

        # Carregamento do arquivo
        try:
            if self.tipo_arquivo == "pdf":
                if self.caminho_arquivo in self.app_mestre.documentos_virtuais:
                    self.bytes_arquivo = self.app_mestre.documentos_virtuais[self.caminho_arquivo]
                else:
                    with open(self.caminho_arquivo, "rb") as arquivo_fisico:
                        self.bytes_arquivo = arquivo_fisico.read()
                self.documento = pymupdf.open(stream=self.bytes_arquivo, filetype="pdf")
                self.total_paginas = len(self.documento)
                for i in range(self.total_paginas):
                    pagina = self.documento[i]
                    if pagina.rotation != 0:
                        self.rotacoes[i] = pagina.rotation
            else:
                self.documento = None
                if self.caminho_arquivo in self.app_mestre.documentos_virtuais:
                    self.bytes_arquivo = self.app_mestre.documentos_virtuais[self.caminho_arquivo]
                else:
                    with open(self.caminho_arquivo, "rb") as arquivo_fisico:
                        self.bytes_arquivo = arquivo_fisico.read()
                self.imagem_pil_original = Image.open(io.BytesIO(self.bytes_arquivo))
                self.imagem_pil_atual = self.imagem_pil_original.copy()
                self.total_paginas = 1
        except Exception as erro_carregamento:
            logger.error(f"Erro Crítico ao carregar arquivo de visualização {self.caminho_arquivo}: {erro_carregamento}")
            messagebox.showerror("Erro Crítico", f"Erro no motor de leitura nativo:\n\n{erro_carregamento}", parent=self)
            self.destroy()
            return

        self.rotacoes_iniciais = deepcopy(self.rotacoes)
        self.criar_widgets()
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        self.atualizar_visualizacao_pagina()

    def _get_app_mestre(self, componente: tk.Misc) -> Any:
        # Busca recursiva pelo pai que detém os documentos_virtuais (JanelaPrincipal)
        mestre = componente
        while mestre is not None:
            if hasattr(mestre, 'documentos_virtuais'):
                return mestre
            mestre = mestre.master
        return componente

    def criar_widgets(self) -> None:
        self.lona_imagem = tk.Canvas(self, bg="lightgray")
        self.lona_imagem.pack(padx=10, pady=10, expand=True, fill="both")

        quadro_controle = tk.Frame(self)
        quadro_controle.pack(pady=10)
        quadro_edicao = tk.Frame(quadro_controle)
        quadro_edicao.pack(pady=(0, 5))

        self.botao_girar_anti_horario = tk.Button(quadro_edicao, text="Girar ↺", command=self.girar_anti_horario)
        self.botao_girar_anti_horario.pack(side="left", padx=5)
        
        self.botao_cortar = tk.Button(quadro_edicao, text="Cortar", command=self.alternar_modo_corte)
        self.botao_cortar.pack(side="left", padx=5)
        
        self.botao_resetar = tk.Button(quadro_edicao, text="Resetar", command=self.redefinir_estado_imagem)
        self.botao_resetar.pack(side="left", padx=5)
        
        self.botao_girar_horario = tk.Button(quadro_edicao, text="Girar ↻", command=self.girar_horario)
        self.botao_girar_horario.pack(side="left", padx=5)

        quadro_navegacao = tk.Frame(quadro_controle)
        quadro_navegacao.pack(pady=(5, 0))
        
        self.botao_anterior = tk.Button(quadro_navegacao, text="<< Anterior", command=self.pagina_anterior)
        self.botao_anterior.pack(side="left", padx=5)
        
        self.rotulo_info_pagina = tk.Label(quadro_navegacao, text="")
        self.rotulo_info_pagina.pack(side="left", padx=10)
        
        self.botao_proxima = tk.Button(quadro_navegacao, text="Próxima >>", command=self.proxima_pagina)
        self.botao_proxima.pack(side="left", padx=5)

        self.lona_imagem.bind("<ButtonPress-1>", self.ao_pressionar_mouse)
        self.lona_imagem.bind("<B1-Motion>", self.ao_arrastar_mouse)
        self.lona_imagem.bind("<ButtonRelease-1>", self.ao_soltar_mouse)
        self.lona_imagem.bind("<Configure>", self.redesenhar_lona)

    def atualizar_visualizacao_pagina(self) -> None:
        if self.tipo_arquivo == "pdf":
            pagina = self.documento[self.indice_pagina_atual]
            rotacao_aplicada = self.rotacoes.get(self.indice_pagina_atual, 0)
            pagina.set_rotation(rotacao_aplicada)
            
            self.pixmap = pagina.get_pixmap()
            paginas_cortadas = list(self.cortes_pagina_pdf.keys())
            
            if self.indice_pagina_atual not in paginas_cortadas:
                self.imagem_pil_atual = Image.frombytes("RGB", [self.pixmap.width, self.pixmap.height], self.pixmap.samples)
            else:
                self.imagem_pil_atual = self.cortes_pagina_pdf[self.indice_pagina_atual]

        self.redesenhar_lona()
        self.rotulo_info_pagina.config(text=f"Página {self.indice_pagina_atual + 1} de {self.total_paginas}")
        self.atualizar_estados_botoes()

    def redesenhar_lona(self, event: Any = None) -> None:
        if not self.imagem_pil_atual: return

        largura_lona = self.lona_imagem.winfo_width()
        altura_lona = self.lona_imagem.winfo_height()

        if largura_lona <= 1 or altura_lona <= 1: return

        imagem_exibir = self.imagem_pil_atual.copy()
        largura_orig, altura_orig = imagem_exibir.size

        imagem_exibir.thumbnail((largura_lona, altura_lona), Image.Resampling.LANCZOS)
        largura_exibida, altura_exibida = imagem_exibir.size

        if largura_exibida > 0:
            self.fator_escala_exibicao = largura_orig / largura_exibida

        self.imagem_tk_foto = ImageTk.PhotoImage(imagem_exibir)

        self.lona_imagem.delete("all")
        self.deslocamento_x_imagem = (largura_lona - largura_exibida) / 2
        self.deslocamento_y_imagem = (altura_lona - altura_exibida) / 2

        self.lona_imagem.create_image(largura_lona / 2, altura_lona / 2, anchor="center", image=self.imagem_tk_foto)

    def aplicar_rotacao(self, angulo: int) -> None:
        if self.tipo_arquivo == "imagem":
            self.imagem_pil_atual = self.imagem_pil_atual.rotate(angulo, expand=True)
            self.imagem_alterada = True
            self.redesenhar_lona()
        else:
            if self.indice_pagina_atual in self.cortes_pagina_pdf:
                self.imagem_pil_atual = self.imagem_pil_atual.rotate(angulo, expand=True)
                self.cortes_pagina_pdf[self.indice_pagina_atual] = self.imagem_pil_atual
            else:
                rotacao_corrente = self.rotacoes.get(self.indice_pagina_atual, 0)
                nova_rotacao = (rotacao_corrente - angulo + 360) % 360
                if nova_rotacao == 0 and self.indice_pagina_atual not in self.rotacoes_iniciais:
                    self.rotacoes.pop(self.indice_pagina_atual, None)
                else:
                    self.rotacoes[self.indice_pagina_atual] = nova_rotacao

            self.atualizar_visualizacao_pagina()

    def girar_horario(self) -> None:
        self.aplicar_rotacao(-90)

    def girar_anti_horario(self) -> None:
        self.aplicar_rotacao(90)

    def alternar_modo_corte(self) -> None:
        self.esta_cortando = not self.esta_cortando
        cursor = "cross" if self.esta_cortando else ""
        relevo = "sunken" if self.esta_cortando else "raised"
        texto = "Cancelar Corte" if self.esta_cortando else "Cortar"
        self.lona_imagem.config(cursor=cursor)
        self.botao_cortar.config(relief=relevo, text=texto)
        if not self.esta_cortando and self.id_retangulo_corte:
            self.lona_imagem.delete(self.id_retangulo_corte)

    def ao_pressionar_mouse(self, evento: tk.Event) -> None:
        if self.esta_cortando:
            self.inicio_corte_x = self.lona_imagem.canvasx(evento.x)
            self.inicio_corte_y = self.lona_imagem.canvasy(evento.y)
            self.id_retangulo_corte = self.lona_imagem.create_rectangle(
                self.inicio_corte_x, self.inicio_corte_y,
                self.inicio_corte_x, self.inicio_corte_y,
                outline="red", width=2, dash=(4, 4)
            )

    def ao_arrastar_mouse(self, evento: tk.Event) -> None:
        if self.esta_cortando and self.id_retangulo_corte:
            cur_x, cur_y = self.lona_imagem.canvasx(evento.x), self.lona_imagem.canvasy(evento.y)
            self.lona_imagem.coords(
                self.id_retangulo_corte, self.inicio_corte_x, self.inicio_corte_y, cur_x, cur_y
            )

    def ao_soltar_mouse(self, evento: tk.Event) -> None:
        if self.esta_cortando:
            fim_x, fim_y = self.lona_imagem.canvasx(evento.x), self.lona_imagem.canvasy(evento.y)
            self.alternar_modo_corte()

            caixa_na_lona = (
                min(self.inicio_corte_x, fim_x), min(self.inicio_corte_y, fim_y),
                max(self.inicio_corte_x, fim_x), max(self.inicio_corte_y, fim_y),
            )

            caixa_na_imagem = (
                caixa_na_lona[0] - self.deslocamento_x_imagem,
                caixa_na_lona[1] - self.deslocamento_y_imagem,
                caixa_na_lona[2] - self.deslocamento_x_imagem,
                caixa_na_lona[3] - self.deslocamento_y_imagem,
            )

            caixa_final = tuple(int(coord * self.fator_escala_exibicao) for coord in caixa_na_imagem)
            self.coordenadas_corte_imagem[self.indice_pagina_atual] = caixa_final
            
            if caixa_final[2] > caixa_final[0] and caixa_final[3] > caixa_final[1]:
                self.imagem_pil_atual = self.imagem_pil_atual.crop(caixa_final)
                self.imagem_alterada = True
                self.redesenhar_lona()
                
            if self.tipo_arquivo == "pdf":
                self.cortes_pagina_pdf[self.indice_pagina_atual] = self.imagem_pil_atual
                self.atualizar_visualizacao_pagina()

    def redefinir_estado_imagem(self) -> None:
        if self.tipo_arquivo == "imagem" and self.imagem_pil_original:
            self.imagem_pil_atual = self.imagem_pil_original.copy()
            self.imagem_alterada = False

        if self.tipo_arquivo == "pdf":
            if self.indice_pagina_atual in self.cortes_pagina_pdf:
                self.cortes_pagina_pdf.pop(self.indice_pagina_atual)
                self.imagem_alterada = False
            if self.rotacoes.get(self.indice_pagina_atual, None):
                self.rotacoes.pop(self.indice_pagina_atual)

        self.atualizar_visualizacao_pagina()

    def ao_fechar(self) -> None:
        pdf_alterado = (self.tipo_arquivo == "pdf" and self.rotacoes != self.rotacoes_iniciais or self.cortes_pagina_pdf)
        if pdf_alterado or self.imagem_alterada:
            self.houve_edicao = True
            try:
                if self.tipo_arquivo == "pdf":
                    if self.cortes_pagina_pdf:
                        for pagina_idx, pagina_cortada in self.cortes_pagina_pdf.items():
                            buffer_corte = io.BytesIO()
                            pagina_cortada.save(buffer_corte, format="png")
                            buffer_corte.seek(0)
                            bytes_corte_imagem = buffer_corte.getvalue()
                            bytes_pagina_refeita = func_converter_imagem_para_pdf(caminho_imagem=bytes_corte_imagem, stream=True)
                            
                            with pymupdf.open(stream=bytes_pagina_refeita, filetype="pdf") as nova_pagina:
                                self.documento.delete_page(pagina_idx)
                                self.documento.insert_pdf(nova_pagina, from_page=0, to_page=0, start_at=pagina_idx)

                    for indice_pag, angulo_rotacao in self.rotacoes.items():
                        self.documento[indice_pag].set_rotation(angulo_rotacao)

                    buffer_saida = io.BytesIO()
                    self.documento.save(buffer_saida, garbage=4, deflate=True)
                    self.documento.close()
                    self.documento.is_closed = True
                    
                    self.app_mestre.documentos_virtuais[self.caminho_arquivo] = buffer_saida.getvalue()
                    logger.info(f"Edições salvas em memória virtual para: {self.caminho_arquivo}")
                else:
                    buffer_saida = io.BytesIO()
                    self.imagem_pil_atual.save(buffer_saida, format=self.imagem_pil_original.format or "PNG", quality=95, subsampling=0)
                    self.app_mestre.documentos_virtuais[self.caminho_arquivo] = buffer_saida.getvalue()
                    logger.info(f"Imagem editada salva em memória virtual para: {self.caminho_arquivo}")
            except Exception as erro_salvamento:
                logger.error(f"Erro agressivo ao persistir edição visual na memória buffer do mestre: {erro_salvamento}")
                    
        if self.tipo_arquivo == "pdf" and not getattr(self.documento, 'is_closed', False):
            self.documento.close()
        self.destroy()

    def proxima_pagina(self) -> None:
        if self.tipo_arquivo == "pdf" and self.indice_pagina_atual < self.total_paginas - 1:
            self.indice_pagina_atual += 1
            self.atualizar_visualizacao_pagina()

    def pagina_anterior(self) -> None:
        if self.indice_pagina_atual > 0:
            self.indice_pagina_atual -= 1
            self.atualizar_visualizacao_pagina()

    def atualizar_estados_botoes(self) -> None:
        eh_pdf = self.tipo_arquivo == "pdf"
        self.botao_anterior.config(state="normal" if eh_pdf and self.indice_pagina_atual > 0 else "disabled")
        self.botao_proxima.config(state="normal" if eh_pdf and self.indice_pagina_atual < self.total_paginas - 1 else "disabled")
