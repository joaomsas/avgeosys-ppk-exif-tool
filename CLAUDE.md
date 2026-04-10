# AVGeoSys — Instruções para o Claude Code

## Release Checklist

A cada nova versão, atualizar TODOS estes arquivos:

| Arquivo | Branch | Campo |
|---------|--------|-------|
| `avgeosys/__init__.py` | `master` | `__version__` |
| `AVGeoSys.iss` | `master` | `AppVersion` |
| `version.json` | `master` **e** `main` | version + url + notes |

### Por que `main` também?

`updater.py` busca atualizações em:
```
https://raw.githubusercontent.com/joaomsas/avgeosys-ppk-exif-tool/main/version.json
```

Atualizar só o `master` deixa o `version.json` no `main` desatualizado — usuários com
versões antigas **não verão o banner de nova versão**.

### Como atualizar o `version.json` no `main` sem merge completo

```bash
git checkout origin/main -b tmp-release
git checkout master -- version.json
git commit -m "chore: bump version.json para vX.Y.Z no main"
git push origin tmp-release:main
git checkout master && git branch -d tmp-release
```
