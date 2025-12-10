Запуск API:
uvicorn main:app --reload --host 127.0.0.1 --port 8000

Запуск worker (в другом терминале / контейнере):
python worker.py
