from gui.main_window import JanelaPrincipal
from utils.logger import logger

if __name__ == "__main__":
    logger.info("Iniciando PDFLab...")
    aplicacao = JanelaPrincipal()
    aplicacao.mainloop()
    logger.info("Encerramento do programa.")
