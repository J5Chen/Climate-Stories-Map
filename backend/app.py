import os

from app.__init__ import create_app
from app.posts_routes import posts_routes_blueprint

app = create_app()
app.register_blueprint(posts_routes_blueprint)


if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=True)