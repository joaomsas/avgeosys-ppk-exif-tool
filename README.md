# AVGeoSys — PPK & EXIF Geotagging Tool

Ferramenta desktop para georreferenciamento preciso de fotos aéreas via PPK (Post-Processed Kinematic), usando RTKLIB e marcadores de tempo MRK.

## Instalação (a partir do código-fonte)

```bash
pip install -e .
```

Dependências: `piexif`, `simplekml`, `pandas`, `numpy`. `pyproj` é opcional (melhora a correção de altitude ortométrica).

## Configuração do RTKLIB

Edite `avgeosys/config.py` e defina `RTKLIB_PATH` para o caminho do executável `rnx2rtkp.exe` na sua máquina:

```python
RTKLIB_PATH: Path = Path(r"C:\RTKLIB\rnx2rtkp.exe")
```

No instalador `.exe`, o `rnx2rtkp.exe` já é incluído automaticamente.

## Uso (GUI)

```bash
python -m avgeosys.ui.tkinter_ui
```

Ou, após `pip install -e .`:

```bash
# via entry_point (CLI principal — adicione flag de GUI futuramente)
avgeosys --help
```

A interface gráfica permite:
- Selecionar o diretório do projeto de voo
- Executar o PPK (gera arquivos `.pos` via rnx2rtkp)
- Executar o Geotag completo (interpolação + escrita de EXIF GPS nas fotos)
- Executar o pipeline completo ("▶ Tudo")
- Visualizar o log em tempo real (colorido por nível)

## Uso (CLI)

```bash
avgeosys /caminho/do/projeto --all --orthometric
avgeosys /caminho/do/projeto --ppk
avgeosys /caminho/do/projeto --interpolate --orthometric
avgeosys /caminho/do/projeto --geotag
avgeosys /caminho/do/projeto --report
```

### Flags disponíveis

| Flag | Descrição |
|------|-----------|
| `PATH` | Diretório raiz do projeto de voo |
| `--ppk` | Executa o PPK com rnx2rtkp |
| `--interpolate` | Interpola coordenadas para cada foto |
| `--geotag` | Escreve EXIF GPS nas fotos JPEG |
| `--report` | Gera `relatorio_processamento.txt` + arquivos KMZ |
| `--all` | Executa o pipeline completo (PPK → interpolação → geotag → relatório) |
| `--orthometric` | Aplica correção de altura ortométrica (geóide) |
| `--verbose` | Ativa logs de debug |
| `--skip-rover-nav` | Ignora o arquivo de navegação do rover |

## Estrutura de arquivos do projeto

```
projeto_voo/
├── rover.YYO          # RINEX observação (rover)
├── base.YYO           # RINEX observação (base)
├── base.YYP           # RINEX navegação (base)
├── voo.MRK            # Marcadores de tempo do drone
└── PPK_Results/       # Criado automaticamente
    ├── flight.pos     # Solução PPK do RTKLIB
    ├── interpolated_data.json
    ├── relatorio_processamento.txt
    ├── resultado_interpolado.kmz
    └── compilado_exif_data.kmz
```

## Distribuição (Windows .exe)

```bash
pip install pyinstaller
pyinstaller AVGeoSys.spec
```

O executável gerado em `dist/AVGeoSys.exe` inclui RTKLIB, configuração PPK e ícone.

Para gerar o instalador Windows, abra `AVGeoSys.iss` no [Inno Setup](https://jrsoftware.org/isinfo.php).
