@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   Publicar o relay no GitHub
echo ==========================================================
echo.

set REPO_URL=%~1
if "%REPO_URL%"=="" (
  echo Cole a URL do repositorio VAZIO que voce criou no GitHub.
  echo Exemplo: https://github.com/seu-usuario/remote-relay.git
  echo.
  set /p REPO_URL="URL do repositorio: "
)

if "%REPO_URL%"=="" (
  echo.
  echo URL vazia. Nada foi feito.
  pause
  exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
  echo git nao encontrado no PATH. Instale o Git for Windows.
  pause
  exit /b 1
)

REM identidade do commit, apenas NESTE repositorio
git config user.name >nul 2>&1
if errorlevel 1 git config user.name "Remote Relay"
git config user.email >nul 2>&1
if errorlevel 1 git config user.email "relay@localhost"

if not exist ".git" (
  echo [1/5] git init
  git init -b main
) else (
  echo [1/5] repositorio git ja existe, reaproveitando
)

echo [2/5] adicionando arquivos
git add -A

echo [3/5] commit
git commit -m "Relay WebSocket para o Remote Control App"

echo [4/5] apontando para o GitHub
git remote remove origin >nul 2>&1
git remote add origin "%REPO_URL%"

echo [5/5] enviando
git branch -M main
git push -u origin main

if errorlevel 1 (
  echo.
  echo O ENVIO FALHOU. Causas comuns:
  echo   - o repositorio no GitHub ainda nao existe
  echo   - o repositorio ja tem arquivo dentro ^(crie VAZIO, sem README^)
  echo   - falta autenticacao: rode "git push -u origin main" na mao e
  echo     faca login na janela que abrir
) else (
  echo.
  echo PRONTO. Os arquivos estao no GitHub.
  echo Agora siga o passo C do LEIA-ME.md ^(Render^).
)

echo.
pause
