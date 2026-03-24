class ExcecaoBasePDF(Exception):
    """
    Exceção base para o projeto PDFLab.
    Serve como ancestral para todas as exceções personalizadas da biblioteca.
    """
    pass

class ErroConversaoPDF(ExcecaoBasePDF):
    """
    Lançada quando ocorre uma falha irreversível durante a conversão
    de uma imagem para PDF ou a extração de páginas de PDF para imagem.
    """
    pass

class ErroMesclagemPDF(ExcecaoBasePDF):
    """
    Lançada quando o sistema encontra um erro crítico ao tentar
    juntar (merge) múltiplos arquivos PDF em um único documento.
    """
    pass

class ErroOtimizacaoImagem(ExcecaoBasePDF):
    """
    Lançada quando o algoritmo não consegue otimizar as dimensões ou
    qualidade de uma imagem dentro dos limites toleráveis de segurança.
    """
    pass

class ErroCompressaoPDF(ExcecaoBasePDF):
    """
    Lançada quando o processamento de recodificação Ghostscript ou similar
    (compressão nativa) falha na redução lógica de um arquivo PDF.
    """
    pass
