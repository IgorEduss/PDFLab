import io
from pathlib import Path
from typing import Literal, Union, Dict, List, Optional, Any

import pymupdf
from PIL import Image

from utils.logger import logger
from core.exceptions import ErroConversaoPDF, ErroMesclagemPDF, ErroCompressaoPDF
from core.image_logic import ajusta_tamanho_imagem

def func_converter_imagem_para_pdf(caminho_imagem: Union[str, bytes], arquivo_saida: Optional[str] = None, stream: bool = False) -> Optional[bytes]:
    """
    Converte uma imagem (presente em arquivo ou alocada na RAM) em uma página única de PDF formato A4.
    
    Parâmetros:
        caminho_imagem (str | bytes): O caminho no disco rígido ou array de bytes pré-anexado na memória.
        arquivo_saida (str | None): O caminho onde gravar o PDF resultante. Requerido caso `stream` seja Falso.
        stream (bool): Se Verdadeiro, não gravará o arquivo físico, devolvendo seu bytestream serializado.
        
    Retorno:
        bytes | None: Caso `stream` for verdadeiro, devolve a matriz transposta, senão devolve nulo de operação silenciosa.
        
    Lança Erros:
        ErroConversaoPDF: Erro se a extração colapsar ou se faltarem argumentos para gravar.
    """
    try:
        if isinstance(caminho_imagem, bytes):
            bytes_imagem = caminho_imagem
            with pymupdf.open(stream=caminho_imagem, filetype="png") as imagem_aberta:
                retangulo = imagem_aberta[0].rect
                largura_img, altura_img = retangulo.width, retangulo.height
        else:
            with pymupdf.open(caminho_imagem) as imagem_aberta:
                retangulo = imagem_aberta[0].rect
                largura_img, altura_img = retangulo.width, retangulo.height
            with open(caminho_imagem, "rb") as arquivo:
                bytes_imagem = arquivo.read()

        largura_a4, altura_a4 = pymupdf.paper_sizes()["a4"]
        with pymupdf.open() as documento_pdf:
            pagina = documento_pdf.new_page()
            
            if largura_img > largura_a4 or altura_img > altura_a4:
                escala_x = largura_a4 / largura_img
                escala_y = altura_a4 / altura_img
                escala_menor = min(escala_x, escala_y)

                nova_larg = largura_img * escala_menor
                nova_alt = altura_img * escala_menor

                deslocamento_x, deslocamento_y = 0, 0
                if nova_alt > nova_larg and nova_alt <= altura_a4:
                    deslocamento_x = (largura_a4 - nova_larg) / 2

                retangulo_alvo = pymupdf.Rect(deslocamento_x, deslocamento_y, deslocamento_x + nova_larg, deslocamento_y + nova_alt)
            else:
                deslocamento_x = (largura_a4 - largura_img) / 2
                deslocamento_y = (altura_a4 - altura_img) / 2
                retangulo_alvo = pymupdf.Rect(deslocamento_x, deslocamento_y, deslocamento_x + largura_img, deslocamento_y + altura_img)

            pagina.insert_image(retangulo_alvo, stream=bytes_imagem)

            if not stream:
                if arquivo_saida:
                    documento_pdf.save(arquivo_saida)
                else:
                    raise ErroConversaoPDF("Arquivo de saída não especificado e não está em modo stream.")
            else:
                return documento_pdf.tobytes()
    except Exception as erro:
        logger.error(f"Erro na conversão de Imagem para a raiz do PDF: {erro}")
        raise ErroConversaoPDF(str(erro))


def func_juntar_pdfs(lista_pdfs: List[str], arquivo_saida: str, conversoes_imagem: Optional[Dict[str, bytes]] = None, documentos_virtuais: Optional[Dict[str, bytes]] = None, tamanho_limite_mb: int = 15, fila: Any = None) -> None:
    """
    Agrupa integralmente uma cadeia linear de PDFs ou fragmentos na RAM em um sumário único. 
    Dispõe de um sub-roteamento inteligente de auto compressão Ghostscript baseada na sobrecarga final de Megabytes.
    
    Parâmetros:
        lista_pdfs (List[str]): Vetores dos fragmentos que deverão compor o montante agregado final.
        arquivo_saida (str): Caminho cimentado final para salvamento em disco.
        conversoes_imagem (Dict[str, bytes]): Dicionário com bytestream mapeando a pré-transformação feita de blocos de Imagem puro.
        documentos_virtuais (Dict[str, bytes]): State Tracker do Cache com edições fantasmas em andamento.
        tamanho_limite_mb (int): Sub-Teto que quando batido alavancará a rotina de restrito redimensionamento global (Default: 15MB).
    """
    if documentos_virtuais is None: documentos_virtuais = {}
    try:
        resultado = pymupdf.open()
        for caminho_pdf in lista_pdfs:
            if conversoes_imagem and caminho_pdf in conversoes_imagem:
                with pymupdf.open(stream=conversoes_imagem[caminho_pdf], filetype="pdf") as arquivo_mesclado:
                    resultado.insert_pdf(arquivo_mesclado)
            else:
                if caminho_pdf in documentos_virtuais:
                    with pymupdf.open(stream=documentos_virtuais[caminho_pdf], filetype="pdf") as arquivo_mesclado:
                        resultado.insert_pdf(arquivo_mesclado)
                else:
                    with pymupdf.open(caminho_pdf) as arquivo_mesclado:
                        resultado.insert_pdf(arquivo_mesclado)
                    
        resultado_bytes = resultado.tobytes()
        tamanho_mb = len(resultado_bytes) / (1024**2)
        
        logger.info(f"Tamanho bruto do PDF mesclado detectado: {tamanho_mb:.2f} MB")
        
        # Salvamento direto, compressão automática removida a pedido do usuário
        resultado.save(arquivo_saida)
            
    except Exception as erro:
        logger.error(f"Falha gravíssima na união unificada de múltiplos PDFs: {erro}")
        raise ErroMesclagemPDF(str(erro))
    finally:
        resultado.close()


def func_comprimir_pdf(arquivo_entrada: Union[str, bytes], arquivo_saida: str, documentos_virtuais: Optional[Dict[str, bytes]] = None, qualidade_imagem: int = 40, nivel_compresao_png: int = 8, fila: Any = None) -> None:
    """
    Desconstrói páginas, varre matrizes e recria imagens internas interceptando as camadas pesadas do PDF.
    Faz downscaling de todos os artefatos visuais não rasterizados.
    """
    if documentos_virtuais is None: documentos_virtuais = {}
    try:
        if isinstance(arquivo_entrada, bytes):
            documento_original = pymupdf.open(stream=arquivo_entrada, filetype="pdf")
        elif arquivo_entrada in documentos_virtuais:
            documento_original = pymupdf.open(stream=documentos_virtuais[arquivo_entrada], filetype="pdf")
        else:
            documento_original = pymupdf.open(arquivo_entrada)
            
        documento_final = pymupdf.open()
        retangulo_a4 = pymupdf.paper_rect("a4")

        total_paginas = len(documento_original)
        for num_pagina, pagina_original in enumerate(documento_original):
            logger.info(f"Comprimindo individualmente Página {num_pagina + 1} de {total_paginas}")
            if fila:
                fila.put({"tipo": "iniciando_arquivo", "total": total_paginas, "atual": num_pagina + 1, "arquivo": f"Página {num_pagina + 1} de {total_paginas}"})
            pagina_final = documento_final.new_page(width=retangulo_a4.width, height=retangulo_a4.height)

            larg_original, alt_original = pagina_original.rect.width, pagina_original.rect.height
            larg_a4, alt_a4 = retangulo_a4.width, retangulo_a4.height

            escala = min(larg_a4 / larg_original, alt_a4 / alt_original)
            nova_largura, nova_altura = larg_original * escala, alt_original * escala
            deslocamento_x, deslocamento_y = (larg_a4 - nova_largura) / 2, (alt_a4 - nova_altura) / 2
            
            retangulo_alvo = pymupdf.Rect(deslocamento_x, deslocamento_y, deslocamento_x + nova_largura, deslocamento_y + nova_altura)
            pagina_final.show_pdf_page(retangulo_alvo, documento_original, pagina_original.number)

            imagens_internas = pagina_final.get_images(full=True)
            for informacao_imagem in imagens_internas:
                # Se smask (máscara de sombra) > 0 pula a recompressão pois quebra a lógica do pixel matrix do PDF.
                if informacao_imagem[1] > 0:
                    continue

                referencia_cruzada = informacao_imagem[0]
                try:
                    imagem_base = documento_final.extract_image(referencia_cruzada)
                    bytes_varredura = imagem_base["image"]
                    imagem_pillow = Image.open(io.BytesIO(bytes_varredura))
                    buffer_imagem = io.BytesIO()

                    # Lidar com Alpha Chanel perfeitamente.
                    if imagem_pillow.mode in ("RGBA", "LA") or (imagem_pillow.mode == "P" and "transparency" in imagem_pillow.info):
                        imagem_pillow.save(buffer_imagem, format="PNG", optimize=True, compress_level=nivel_compresao_png)
                    else:
                        if imagem_pillow.mode != "RGB":
                            imagem_pillow = imagem_pillow.convert("RGB")
                        imagem_pillow.save(buffer_imagem, format="JPEG", quality=qualidade_imagem, optimize=True)

                    bytes_comprimidos = buffer_imagem.getvalue()

                    if hasattr(pagina_final, "replace_image"):
                        pagina_final.replace_image(referencia_cruzada, stream=bytes_comprimidos)
                    else:
                        retangulos = pagina_final.get_image_rects(referencia_cruzada)[0]
                        pagina_final.delete_image(referencia_cruzada)
                        pagina_final.insert_image(retangulos, stream=bytes_comprimidos)

                except Exception as erro_local:
                    logger.warning(f"Não foi possível reprocessar a imagem interceptada [{referencia_cruzada}]: {erro_local}")

        documento_final.save(arquivo_saida, garbage=4, deflate=True, clean=True)
        
    except Exception as erro:
        logger.error(f"Falha generalizada no encolhimento iterativo do PDF: {erro}")
        raise ErroCompressaoPDF(str(erro))
    finally:
        if 'documento_original' in locals():
            documento_original.close()
        if 'documento_final' in locals():
            documento_final.close()


def func_converter_pdf_imagem(caminho_pdf: str, documentos_virtuais: Optional[Dict[str, bytes]] = None) -> None:
    """
    Desmembra fisicamente o arquivo multipágina integral varrendo a árvore mestre do documento, transformando 
    cada folha em artefatos PNG otimizados pelo Fator Cinto de Segurança V2, diretamente persistidos em disco.
    """
    if documentos_virtuais is None: documentos_virtuais = {}
    try:
        if caminho_pdf in documentos_virtuais:
            contexto_pdf = pymupdf.open(stream=documentos_virtuais[caminho_pdf], filetype="pdf")
        else:
            contexto_pdf = pymupdf.open(caminho_pdf)
            
        with contexto_pdf as pasta_documentos:
            import re
            from datetime import datetime
            origem_raiz = Path(caminho_pdf).parent
            nome_mestre = Path(caminho_pdf).stem
            sufixo = datetime.now().strftime("_%y%m%d_%H%M%S")
            padrao = re.compile(r"_\d{6,8}_\d{6}$")
            nome_limpo = padrao.sub("", nome_mestre)
            
            for i, folha in enumerate(pasta_documentos):
                matriz_linear = pymupdf.Matrix(1.0, 1.0)
                mapa_pixels = folha.get_pixmap(matrix=matriz_linear)
                imagem_pil = mapa_pixels.pil_image()
                buffer_visual = io.BytesIO()
                imagem_pil.save(buffer_visual, format='PNG')
                
                caminho_extrato_salvamento = origem_raiz / f"{nome_limpo}{sufixo}_{i+1}.png"
                # O processador se recicla contra OOM (Out Of Memory) usando o Resampler do módulo Pillow Imagem nativa.
                ajusta_tamanho_imagem(buffer_visual, caminho_salvamento=caminho_extrato_salvamento, extensao="PNG")
    except Exception as erro:
        logger.error(f"Erro brutal fatiando matriz de PDF do caminho ({caminho_pdf}): {erro}")
        raise ErroConversaoPDF(str(erro))
