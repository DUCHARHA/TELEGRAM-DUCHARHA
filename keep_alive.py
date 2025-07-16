from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Бот работает!</h1>"

@app.route('/favicon.ico')
def favicon():
    return '', 204  # Возвращаем пустой ответ без ошибки

def run():
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start() 