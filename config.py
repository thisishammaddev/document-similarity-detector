import os

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'plagiarism_detector_super_secret_key_123!'
    
    # Database configuration
    # Using SQLite for simpler setup - database will be in a file named 'plagiarism_detector.db'
    # in the project's instance folder (or root if instance_path isn't configured for Flask app explicitly)
    # For simplicity, we'll place it in the root.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'plagiarism_detector.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File upload settings
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Create upload folder if it doesn't exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True # Log SQL queries

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Add any production-specific settings here, e.g., logging, security headers

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    # For testing, use an in-memory SQLite database or a separate test file
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'plagiarism_detector_test.db')
    # SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:" # Alternative for even faster tests (data lost on close)
    WTF_CSRF_ENABLED = False # Disable CSRF forms for testing

# Dictionary to access config classes by name
config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig,
    default=DevelopmentConfig
)

# Function to get the appropriate config
def get_config_by_name(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')
    return config_by_name.get(config_name, DevelopmentConfig)

# Example of how to get the current configuration
# current_config = get_config_by_name()