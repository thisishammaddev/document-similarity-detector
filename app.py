import os
from flask import Flask, request, render_template, redirect, url_for, flash, session as flask_session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import exc as sqlalchemy_exc

from config import get_config_by_name
from plagiarism_detector.models import Base, User, Document, SimilarityReport, UserRole, engine as db_engine
from plagiarism_detector.utils import extract_text_from_file, preprocess_text, calculate_similarity, generate_content_hash

# Initialize Flask App
app = Flask(__name__)
app_config = get_config_by_name(os.getenv('FLASK_CONFIG'))
app.config.from_object(app_config)

# Database Setup
Session = scoped_session(sessionmaker(bind=db_engine))
Base.metadata.create_all(bind=db_engine) # Create tables if they don't exist

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Helper Functions ---
def get_db_session():
    return Session()

@app.teardown_appcontext
def remove_session(exception=None):
    Session.remove()

# --- Routes ---

@app.route('/')
def index():
    db_sess = get_db_session()
    user_id = flask_session.get('user_id')
    user = None
    if user_id:
        user = db_sess.query(User).filter_by(id=user_id).first()
    
    # For simplicity, just show all documents for now.
    # In a real app, you'd filter by user or role.
    documents = db_sess.query(Document).order_by(Document.upload_date.desc()).all()
    return render_template('index.html', user=user, documents=documents, title="Home")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if flask_session.get('user_id'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        # role = request.form.get('role', 'student') # Default to student, admin creation might be separate

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html', title="Register")

        db_sess = get_db_session()
        existing_user = db_sess.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'warning')
            return render_template('register.html', title="Register")

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username, 
            email=email, 
            password_hash=hashed_password,
            role=UserRole.STUDENT # Or parse from form if admin registration is allowed
        )
        try:
            db_sess.add(new_user)
            db_sess.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlalchemy_exc.IntegrityError:
            db_sess.rollback()
            flash('An error occurred. Username or email might already be taken.', 'danger')
        except Exception as e:
            db_sess.rollback()
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            
    return render_template('register.html', title="Register")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask_session.get('user_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')

        if not username_or_email or not password:
            flash('Username/Email and password are required.', 'danger')
            return render_template('login.html', title="Login")

        db_sess = get_db_session()
        user = db_sess.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            flask_session['user_id'] = user.id
            flask_session['username'] = user.username
            flask_session['role'] = user.role.value # Store role value
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password.', 'danger')
            
    return render_template('login.html', title="Login")

@app.route('/logout')
def logout():
    flask_session.pop('user_id', None)
    flask_session.pop('username', None)
    flask_session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    user_id = flask_session.get('user_id')
    if not user_id:
        flash('You must be logged in to upload documents.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            # Save file temporarily to process it
            temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(temp_filepath)
            
            db_sess = get_db_session() # Initialize db_sess earlier
            raw_text = None # Initialize raw_text

            try:
                raw_text = extract_text_from_file(temp_filepath)
                if not raw_text or not raw_text.strip(): # Check for None or empty string
                    flash('The uploaded file is empty or could not be read.', 'warning')
                    # No db operation yet, so no rollback needed here
                    return redirect(request.url) # temp_filepath will be removed in finally

                content_hash = generate_content_hash(raw_text)
                existing_document = db_sess.query(Document).filter_by(content_hash=content_hash).first()

                if existing_document:
                    flash(f'This exact document (or one with identical content) already exists in the database (ID: {existing_document.id}).', 'info')
                    return redirect(url_for('view_document', doc_id=existing_document.id)) # temp_filepath will be removed in finally

                # processed_text is calculated here, if it fails, raw_text is still available for error reporting
                # but the NLTK error is the primary concern for processed_text
                # For now, let's assume if raw_text is fine, we proceed.
                # The NLTK error will be caught by the generic Exception.

                new_doc = Document(
                    filename=original_filename,
                    original_filename=file.filename,
                    text_content=raw_text,
                    content_hash=content_hash,
                    uploader_id=user_id,
                    file_type=original_filename.rsplit('.', 1)[1].lower()
                )
                db_sess.add(new_doc)
                db_sess.commit() # Commit new document
                
                flash(f'Document "{original_filename}" uploaded successfully! Now checking for plagiarism...', 'success')
                
                # Trigger plagiarism check in a separate try-except block or make it more robust
                try:
                    check_plagiarism_for_document(new_doc.id, db_sess) # db_sess is already committed for new_doc
                except Exception as plag_check_e:
                    # Log this error, but the document is already saved.
                    print(f"Error during plagiarism check for doc ID {new_doc.id}: {plag_check_e}")
                    flash(f'Document saved, but an error occurred during plagiarism check: {plag_check_e}', 'warning')
                
                return redirect(url_for('view_document', doc_id=new_doc.id))

            except ValueError as e: # From extract_text_from_file for unsupported types or bad PDF
                db_sess.rollback() # Rollback any potential partial transaction
                flash(str(e), 'danger')
                return redirect(request.url)
            except Exception as e:
                db_sess.rollback() # Rollback any potential partial transaction
                # Check if the error is the NLTK LookupError for 'punkt_tab'
                if isinstance(e, LookupError) and 'punkt_tab' in str(e):
                     error_message = "NLTK 'punkt_tab' resource not found. Please ensure NLTK's 'punkt' tokenizer is fully installed. This may require running `import nltk; nltk.download('punkt')` in a Python console if automatic downloads fail."
                elif isinstance(e, PermissionError) and 'os.remove' in str(e): # This shouldn't happen if finally is used correctly
                    error_message = f"Could not clean up temporary file. {str(e)}"
                else:
                    error_message = f'An error occurred during file processing or database operation: {str(e)}'
                flash(error_message, 'danger')
                return redirect(request.url)
            finally:
                # Ensure temporary file is always removed
                if os.path.exists(temp_filepath):
                    try:
                        os.remove(temp_filepath)
                    except PermissionError as pe:
                        print(f"Warning: Could not remove temp file {temp_filepath} due to PermissionError: {pe}")
                    except Exception as e_remove:
                         print(f"Warning: Error removing temp file {temp_filepath}: {e_remove}")
        else:
            flash(f'File type not allowed. Allowed types are: {", ".join(app.config["ALLOWED_EXTENSIONS"])}', 'danger')
            return redirect(request.url)

    return render_template('upload.html', title="Upload Document")

def check_plagiarism_for_document(new_doc_id, db_sess):
    """
    Compares a newly uploaded document against all existing documents in the database.
    """
    new_document = db_sess.query(Document).filter_by(id=new_doc_id).first()
    if not new_document:
        print(f"Error: Document with ID {new_doc_id} not found for plagiarism check.")
        return

    processed_new_text = preprocess_text(new_document.text_content)
    if not processed_new_text:
        print(f"Warning: Document ID {new_doc_id} resulted in empty text after preprocessing. Skipping.")
        return

    # Compare against all *other* documents
    existing_documents = db_sess.query(Document).filter(Document.id != new_doc_id).all()
    
    reports_created = 0
    for existing_doc in existing_documents:
        processed_existing_text = preprocess_text(existing_doc.text_content)
        if not processed_existing_text:
            # print(f"Skipping comparison with empty document ID {existing_doc.id}")
            continue

        similarity_score = calculate_similarity(processed_new_text, processed_existing_text)

        # Store report if similarity is above a certain threshold (e.g., 0.01 to avoid storing for completely dissimilar)
        # Or store all comparisons, depending on requirements.
        # For now, let's store if there's any similarity.
        if similarity_score > 0.0: # You might want a higher threshold
            report = SimilarityReport(
                new_document_id=new_document.id,
                existing_document_id=existing_doc.id,
                similarity_score=similarity_score,
                report_details=f"TF-IDF Cosine Similarity: {similarity_score:.4f}", # Basic detail
                generated_by_id=new_document.uploader_id # The user who uploaded the new doc
            )
            db_sess.add(report)
            reports_created +=1
    
    if reports_created > 0:
        try:
            db_sess.commit()
            print(f"Created {reports_created} similarity reports for document ID {new_doc_id}.")
        except Exception as e:
            db_sess.rollback()
            print(f"Error saving similarity reports for document ID {new_doc_id}: {str(e)}")
    else:
        print(f"No significant similarities found for document ID {new_doc_id} or no other documents to compare against.")


@app.route('/document/<int:doc_id>')
def view_document(doc_id):
    user_id = flask_session.get('user_id')
    if not user_id:
        flash('You must be logged in to view documents.', 'warning')
        return redirect(url_for('login'))

    db_sess = get_db_session()
    doc = db_sess.query(Document).filter_by(id=doc_id).first_or_404()
    
    # Check if user is admin or owner of the document
    current_user = db_sess.query(User).filter_by(id=user_id).first()
    if not current_user or (current_user.role != UserRole.ADMIN and doc.uploader_id != user_id):
        flash('You do not have permission to view this document.', 'danger')
        return redirect(url_for('index'))

    # Fetch similarity reports where this document is the "new" document
    reports = db_sess.query(SimilarityReport)\
        .filter(SimilarityReport.new_document_id == doc_id)\
        .order_by(SimilarityReport.similarity_score.desc())\
        .all()
        
    return render_template('view_document.html', document=doc, reports=reports, title=f"Document: {doc.original_filename}")

@app.route('/reports')
def list_reports():
    user_id = flask_session.get('user_id')
    if not user_id:
        flash('You must be logged in to view reports.', 'warning')
        return redirect(url_for('login'))

    db_sess = get_db_session()
    current_user = db_sess.query(User).filter_by(id=user_id).first()
    
    query = db_sess.query(SimilarityReport).order_by(SimilarityReport.generated_at.desc())
    
    if current_user.role != UserRole.ADMIN:
        # Students see reports for documents they uploaded
        query = query.join(Document, SimilarityReport.new_document_id == Document.id)\
                     .filter(Document.uploader_id == user_id)
    
    all_reports = query.all()
    return render_template('list_reports.html', reports=all_reports, user=current_user, title="All Similarity Reports")


# --- Admin Routes (Example) ---
@app.route('/admin/users')
def admin_users():
    user_id = flask_session.get('user_id')
    role = flask_session.get('role')
    if not user_id or role != UserRole.ADMIN.value:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('index'))
    
    db_sess = get_db_session()
    users = db_sess.query(User).all()
    return render_template('admin_users.html', users=users, title="Manage Users")


if __name__ == '__main__':
    # For development:
    # 1. Ensure NLTK data is downloaded (see utils.py)
    # 2. Set FLASK_APP=app.py
    # 3. Set FLASK_ENV=development (or FLASK_DEBUG=1)
    # 4. Set DATABASE_URL in your environment or config.py
    # 5. Run: flask run
    #
    # To create an initial admin user (example, do this via a script or manually in DB):
    # from werkzeug.security import generate_password_hash
    # from plagiarism_detector.models import User, UserRole, SessionLocal
    # db = SessionLocal()
    # admin_user = User(username="admin", email="admin@example.com", password_hash=generate_password_hash("adminpass"), role=UserRole.ADMIN)
    # try:
    #   db.add(admin_user)
    #   db.commit()
    #   print("Admin user created.")
    # except Exception as e:
    #   db.rollback()
    #   print(f"Error creating admin: {e}")
    # finally:
    #   db.close()
    
    app.run(debug=app_config.DEBUG)