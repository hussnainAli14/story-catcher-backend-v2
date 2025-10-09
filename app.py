from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
    
    # Register blueprints
    from routes.story_routes import story_bp
    from routes.auth_routes import auth_bp
    from routes.submissions_routes import submissions_bp
    app.register_blueprint(story_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(submissions_bp, url_prefix='/api')
    
    return app

# Create the app instance for Gunicorn
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
