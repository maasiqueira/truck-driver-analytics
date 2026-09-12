# Publicar no GitHub (maasiqueira)

Perfil: **https://github.com/maasiqueira**  
Repositório sugerido: **https://github.com/maasiqueira/truck-driver-analytics**

## No seu PC (Windows)

1. Instale [Git for Windows](https://git-scm.com/download/win) e [GitHub CLI](https://cli.github.com/) (`gh`).
2. Autentique:

```powershell
gh auth login
```

3. Na pasta do projeto:

```powershell
cd C:\Users\Marcus\Projects\truck-driver-analytics
git init
git add .
git commit -m "Add EAI-Nano-TB RV1126 support with microSD recording"
gh repo create maasiqueira/truck-driver-analytics --public --source=. --remote=origin --push
```

Se o repositório **já existir**:

```powershell
git remote add origin https://github.com/maasiqueira/truck-driver-analytics.git
git branch -M main
git push -u origin main
```

## Na placa EAI-Nano-TB

```bash
git clone https://github.com/maasiqueira/truck-driver-analytics.git
cd truck-driver-analytics
bash deploy/scripts/install_eai_nano_tb.sh
```

Atualizar versão em campo:

```bash
cd ~/truck-driver-analytics
git pull
source .venv/bin/activate
pip install -e ".[embedded]"   # na placa EAI (sem PyTorch)
sudo systemctl restart tda-eai-nano
```

## O que não commitar

- `data/runtime/`, vídeos, `*.db`, `models/weights/*.onnx` grandes (ver `.gitignore`)
- Dados de sessão do microSD — backup separado
