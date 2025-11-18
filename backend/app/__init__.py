# app/__init__.py
from flask import Flask

from admin.__init__ import init_admin
from admin.auth import Auth
from app.config import Config
from app.extensions import cors, mongo

#from app.routes import register_blueprints
from swagger import init_swagger

auth = []

def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/")
    app.config.from_object(Config)

    # Initialize core extensions
    mongo.init_app(app)
    cors.init_app(app)
    init_swagger(app)

    # Initialize app logic
    auth = Auth(app)
    init_admin(app)

    # Register all routes
    #register_blueprints(app)

    return app
