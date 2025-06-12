# AVGeoSys - PPK & EXIF Tool

AVGeoSys é um utilitário em Python para processamento PPK, interpolação de posições e atualização de dados EXIF em fotos georreferenciadas. O projeto inclui uma interface de linha de comando simples e pode ser utilizado em Linux ou Windows.

## Instalação

Recomenda-se o uso de um ambiente virtual. Após clonar o repositório, execute:

```bash
python -m pip install --upgrade pip
pip install -e .
```

Para habilitar o cálculo opcional do geóide com o PROJ, instale também
`pyproj`:

```bash
pip install pyproj
```

Os testes utilizam `pytest`, `flake8` e `mypy`, que são instalados automaticamente na CI. Para executá-los localmente:

```bash
pip install pytest flake8 mypy
pytest
```

O executável `rnx2rtkp.exe` do RTKLIB deve estar disponível no diretório base do projeto para o processamento PPK.

## Uso da CLI

O comando principal é `avgeosys` e aceita diversas opções:

```bash
avgeosys PATH [--ppk] [--interpolate] [--geotag] [--orthometric] [--report] [--field-upload] [--all] [--verbose]
```

Use `--orthometric` para gravar altitude ortométrica (altura sobre o geóide) durante o geotagging.

Um fluxo completo pode ser executado com:

```bash
avgeosys /caminho/para/projeto --all
```

Os dados de exemplo em `tests/data` podem ser utilizados para validar a execução.

## Contribuição

Pull requests são bem-vindos. Certifique-se de que os testes estejam passando (`pytest`) e que `flake8` e `mypy` não apresentem erros antes de enviar.
