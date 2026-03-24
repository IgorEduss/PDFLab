import io
import math
from pathlib import Path
from typing import Literal, Union

from PIL import Image

from utils.logger import logger
from core.exceptions import ErroOtimizacaoImagem

LIMITE_INFERIOR_BYTES = 102400  # 100 KB
LIMITE_SUPERIOR_BYTES = 4194304  # 4 MB
MAX_ITERACOES_V2 = 5  # O novo algoritmo é muito mais preciso, 5 é um ótimo cinto de segurança.


def obter_tamanho_bytes(objeto_imagem: Union[Image.Image, str], formato_string: Literal["PNG", "JPEG"] = "PNG") -> int:
    """
    Calcula e retorna o tamanho projetado de uma imagem em bytes no disco.
    
    Parâmetros:
        objeto_imagem (Image.Image | str): Instância do Pillow Image ou string do caminho.
        formato_string (Literal["PNG", "JPEG"]): O formato de saída opcional para a estimativa.
        
    Retorno:
        int: Tamanho projetado em bytes da imagem; devolve 0 em falhas de simulação P/B.
    """
    try:
        buffer = io.BytesIO()
        objeto_imagem.save(buffer, format=formato_string)
        return buffer.tell()
    except Exception as erro:
        logger.error(f"Erro ao obter tamanho da imagem na memória: {erro}")
        return 0


def ajusta_tamanho_imagem(caminho: Union[str, io.BytesIO], caminho_salvamento: Union[str, Path], extensao: Literal["PNG", "JPEG"] = "PNG") -> bool:
    """
    Ajusta iterativamente a escala e resolução da imagem para que o peso do arquivo se
    mantenha dentro da faixa ótima delimitada (100 KB a 4 MB) preparada para PDFs limpos.
    
    Utiliza um cálculo muito veloz via Fator de Área e Raiz Quadrada.
    
    Parâmetros:
        caminho (str | io.BytesIO): Caminho do arquivo ou pacote de bytes virtuais contendo a imagem.
        caminho_salvamento (str | Path): Caminho de saída onde gravar o arquivo na persistência de disco.
        extensao (Literal["PNG", "JPEG"]): O codec adotado para a escrita nativa Pillow.
        
    Retorno:
        bool: Retorna True em caso de sucesso absoluto.
        
    Lança Erros:
        ErroOtimizacaoImagem: Estoura quando o disco ou motor pillow rejeitam a extração fina.
    """
    if isinstance(caminho, str):
        imagem = Image.open(caminho)
    else:  # Já é um BytesIO na memória virtual
        caminho.seek(0)
        imagem = Image.open(caminho)

    for i in range(MAX_ITERACOES_V2):
        tamanho_atual_bytes = obter_tamanho_bytes(imagem, extensao)
        
        # Já está no tamanho favorável de inércia (ou pifou tragicamente ao calcular)
        if (LIMITE_INFERIOR_BYTES <= tamanho_atual_bytes <= LIMITE_SUPERIOR_BYTES) or tamanho_atual_bytes == 0:
            imagem.save(caminho_salvamento, format=extensao)
            return True

        atual_largura, atual_altura = imagem.size
        
        # Queremos mirar no meio da janela predefinida para saltar sem precisar errar
        tamanho_alvo_bytes = (LIMITE_INFERIOR_BYTES + LIMITE_SUPERIOR_BYTES) // 2
        fator_area = tamanho_alvo_bytes / tamanho_atual_bytes
        
        # Escala linear computacional é a exata raiz quadrada da escala da área
        fator_escala = math.sqrt(fator_area)
        
        # No caso de estarmos quase lá, podemos amaciar um pouco a escala paramétrica
        fator_escala = (fator_escala + 1) / 2.0  
        
        nova_largura = int(atual_largura * fator_escala)
        nova_altura = int(atual_altura * fator_escala)

        logger.info(f"Otimizando imagem - Iteração {i+1}: Tamanho={tamanho_atual_bytes}B, Modificando {atual_largura}x{atual_altura} -> {nova_largura}x{nova_altura}")

        if nova_largura <= 0 or nova_altura <= 0:
            logger.warning("Fator de escala colapsou para dimensões nulas. Cancelando laço de repetição.")
            break

        imagem = imagem.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)

    try:
        # Pós-Looping: gravamos em regime de melhor-esforço caso a margem falhou aos topes.
        imagem.save(caminho_salvamento, format=extensao)
        return True
    except Exception as erro:
        logger.error(f"Falha catástrófica na gravação do binário da Imagem: {erro}")
        raise ErroOtimizacaoImagem(f"Não pôde despejar os bytes modificados da imagem em disco: {erro}")
