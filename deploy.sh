#!/bin/bash
# Деплой Smeta_app backend:
#  - git pull
#  - перезапуск контейнера (volume-mount подхватит изменения)
set -e
cd /opt/Smeta_app

CHANGES=$(git status --short)
if [ -n "$CHANGES" ]; then
  echo "WARN: рабочая директория грязная — пропускаю git pull"
  echo "$CHANGES"
else
  git pull origin main
fi

# settings.json должен существовать (не в репо!)
if [ ! -f backend/settings.json ]; then
  echo "✗ backend/settings.json отсутствует — скопируйте из settings.example.json и впишите API-ключ"
  exit 1
fi

# Перезапуск контейнера
docker restart smeta-backend
sleep 3
HEALTH=$(curl -sk -o /dev/null -w '%{http_code}' http://127.0.0.1:8002/)
echo "smeta-backend: HTTP $HEALTH"

echo "Деплой Smeta_app завершён."
