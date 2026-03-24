# PDFLab

PDFLab é um utilitário desktop para manipulação, visualização e reorganização de arquivos PDF. Desenvolvido em Python, o aplicativo oferece uma interface gráfica amigável para facilitar operações comuns com PDFs e imagens iterativas da sua rotina.

## :hammer_and_wrench: Tecnologias / Stack

O projeto utiliza as seguintes tecnologias:

- **Python 3.13+**: Linguagem principal do projeto.
- **Tkinter / Interface Gráfica**: Módulos para a criação das janelas e visualização.
- **PyMuPDF**: Biblioteca robusta (pymupdf) de alta performance para renderizar e manipular documentos PDF.
- **Pillow**: Usada para processamento e controle de imagens geradas em memória a partir do PDF.
- **uv**: Moderno e ultra-rápido gerenciador de dependências e ambientes do Python (organizado pelo arquivo `pyproject.toml` e `uv.lock`).
- **PyInstaller**: Ferramenta utilizada para converter e empacotar a aplicação em um executável autônomo.

## :rocket: Como utilizar e executar o código-fonte

Para executar o código na sua máquina local de desenvolvimento, é necessário ter o Python (>= 3.13) instalado. Se você utiliza o moderno **[uv](https://docs.astral.sh/uv/)**, o processo é mais ágil, mas também é perfeitamente possível usar as ferramentas padrões do Python.

1. Abra o terminal na raiz do projeto onde está o arquivo `pyproject.toml`.
2. Siga os passos correspondentes ao seu ambiente:

### Opção A: Usando o `uv` (Recomendado)
Apenas instale as dependências e inicie de uma vez:
```bash
uv sync
uv run main.py
```

### Opção B: Usando `pip` e ambiente virtual (Tradicional)
Crie um ambiente virtual, ative-o e instale as dependências pelo `pyproject.toml` usando pip:
```bash
# Crie o ambiente virtual
python -m venv .venv

# Ative o ambiente 
.venv\Scripts\activate   # Usuários de Windows
# source .venv/bin/activate # Usuários de macOS/Linux

# Instale as dependências
pip install .

# Execute o programa
python main.py
```

## :package: Como criar um executável com o PyInstaller

Se você deseja distribuir o seu aplicativo para outras pessoas (ou simplesmente utilizá-lo sem abrir o código), você pode gerar um executável `.exe` para o Windows usando o **PyInstaller**, que já se encontra nas dependências do projeto.

Execute o comando abaixo no seu terminal na raiz do projeto, de acordo com o ambiente que configurou acima:

**Se tiver instalado usando `uv`**:
```bash
uv run pyinstaller --name "PDFLab" --windowed --onefile main.py
```

**Se estiver usando o ambiente virtual com o `pip`** (com a `.venv` ativada):
```bash
pyinstaller --name "PDFLab" --windowed --onefile main.py
```

### Entendendo os parâmetros:
* `--name "PDFLab"`: Altera o nome do arquivo resultante de entrada. O executável sairá como `PDFLab.exe`.
* `--windowed` (ou `-w`): Esse parâmetro é essencial para aplicativos GUI (Graphical User Interface). Ele oculta aquela janela preta de terminal (prompt de comando) deixando apenas a janela da sua aplicação aparecer.
* `--onefile` (ou `-F`): Junta todo o código, dependências e interpretador do Python em um agrupamento de apenas **um arquivo único** `.exe`, simplificando a distribuição.

### Onde encontro o arquivo limpo?
Ao finalizar o processo, procure seu aplicativo final pronto em uma nova pasta chamada **`dist`** que será criada na raiz deste projeto.
