from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from flask_migrate import upgrade

from utils import setup_routes
from config import create_app

app = create_app()

setup_routes(app)

CORS(app)

# Swagger configuration
SWAGGER_URL = "/swagger"
API_URL = "/static/swagger.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "InvestLink"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    with app.app_context():
        upgrade()
    app.run(host="0.0.0.0", port=5000, debug=True)
