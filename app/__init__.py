import os
from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO()


def create_app():
    static_dir = os.path.join(os.path.dirname(__file__), 'web', 'static')
    app = Flask(__name__, static_folder=static_dir, static_url_path='/static')
    app.config['SECRET_KEY'] = os.urandom(24)

    from .web.routes import api_bp
    app.register_blueprint(api_bp)

    socketio.init_app(app, async_mode='eventlet', cors_allowed_origins='*')

    from .web.socketio_events import register_events
    register_events()

    return app
