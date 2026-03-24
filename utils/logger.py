import logging
import sys
from pathlib import Path

def configurar_logger(nome: str = "PDFLab") -> logging.Logger:
    """
    Configura e retorna o logger universal da aplicação.
    
    Este método garante que todos os logs sejam gravados simultaneamente em um arquivo 
    físico na raiz ('app.log') e ecoados no terminal para debug em tempo real.

    Parâmetros:
        nome (str): O identificador interno do módulo que está logando. Padrão: "PDFLab".

    Retorno:
        logging.Logger: Instância configurada pronta para receber os comandos `.info`, `.error`, etc.
    """
    registrador = logging.getLogger(nome)
    
    if not registrador.handlers:
        registrador.setLevel(logging.INFO)
        
        formatador = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Rotina de salvamento em Arquivo (app.log)
        caminho_arquivo_log = Path(__file__).parent.parent / "app.log"
        manipulador_arquivo = logging.FileHandler(caminho_arquivo_log, mode='a', encoding='utf-8')
        manipulador_arquivo.setFormatter(formatador)
        
        # Rotina de exibição em Console (Terminal)
        manipulador_console = logging.StreamHandler(sys.stdout)
        manipulador_console.setFormatter(formatador)
        
        registrador.addHandler(manipulador_arquivo)
        registrador.addHandler(manipulador_console)
        
    return registrador

logger = configurar_logger()
