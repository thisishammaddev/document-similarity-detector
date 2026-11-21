import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
from docx import Document as DocxDocument
from pdfminer.high_level import extract_text as extract_text_from_pdf
import os

# Download necessary NLTK data (run this once)
# Ensure these resources are available.
_nltk_resources = [
    ('corpora/stopwords', 'stopwords'),
    ('tokenizers/punkt', 'punkt'),
    ('corpora/wordnet', 'wordnet'),
    ('corpora/omw-1.4', 'omw-1.4') # WordNet 1.4 is often needed by WordNetLemmatizer
]

for path, name in _nltk_resources:
    try:
        nltk.data.find(path)
    except nltk.downloader.DownloadError:
        print(f"NLTK resource {name} not found. Downloading...")
        nltk.download(name, quiet=True)
    except LookupError: # Fallback for older NLTK versions or different error types
        print(f"NLTK resource {name} not found (LookupError). Downloading...")
        nltk.download(name, quiet=True)


# --- Text Extraction ---
def extract_text_from_file(filepath):
    """Extracts raw text from .txt, .docx, or .pdf files."""
    _, extension = os.path.splitext(filepath)
    extension = extension.lower()

    if extension == '.txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    elif extension == '.docx':
        doc = DocxDocument(filepath)
        return "\n".join([para.text for para in doc.paragraphs])
    elif extension == '.pdf':
        return extract_text_from_pdf(filepath)
    else:
        raise ValueError(f"Unsupported file type: {extension}. Only .txt, .docx, .pdf are supported.")

# --- Text Preprocessing ---
def preprocess_text(text):
    """
    Tokenizes, removes stopwords, performs stemming/lemmatization,
    and normalizes text (lowercase, punctuation removal).
    """
    if not text:
        return ""
        
    # 1. Lowercasing
    text = text.lower()

    # 2. Punctuation removal (allow basic sentence structure for phrase matching if needed later)
    text = re.sub(r'[^\w\s\.\-\']', '', text) # Keep periods, hyphens, apostrophes for now
    text = re.sub(r'\s+', ' ', text).strip() # Normalize whitespace

    # 3. Tokenization
    # Ensure 'punkt' is available (already handled by download logic at the top)
    # Attempting to use RegexpTokenizer as a workaround for persistent 'punkt_tab' issues.
    try:
        # A simple regex tokenizer that splits on whitespace and keeps alphanumeric words
        # It also handles punctuation by splitting them as separate tokens if attached to words,
        # or keeping them if they are standalone.
        # This regex aims to be somewhat similar to word_tokenize for basic cases.
        tokenizer = nltk.tokenize.RegexpTokenizer(r'\w+|[^\w\s]')
        tokens = tokenizer.tokenize(text)
        # Filter out any empty strings that might result from the regex
        tokens = [token for token in tokens if token]
    except Exception as e:
        print(f"Error during RegexpTokenizer tokenization: {e}. Falling back to simple split.")
        tokens = text.split()

    # 4. Stopword removal
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words and len(word) > 1] # also remove single char tokens

    # 5. Stemming (PorterStemmer) or Lemmatization (WordNetLemmatizer)
    # Lemmatization is generally preferred for better accuracy.
    lemmatizer = WordNetLemmatizer()
    processed_tokens = [lemmatizer.lemmatize(token) for token in filtered_tokens]
    # stemmer = PorterStemmer()
    # processed_tokens = [stemmer.stem(token) for token in filtered_tokens]

    return " ".join(processed_tokens)


# --- Plagiarism Detection ---
def calculate_similarity(text1, text2):
    """
    Calculates cosine similarity between two texts using TF-IDF.
    Returns a similarity score between 0 and 1.
    """
    if not text1 or not text2:
        return 0.0

    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        # If one of the documents is empty or has no common terms after vectorization,
        # the matrix might have an unexpected shape or result in errors.
        if tfidf_matrix.shape[0] < 2: # Not enough documents to compare
            return 0.0
        # Check if vocabulary is empty (e.g., if texts only contained stopwords)
        if not vectorizer.vocabulary_:
            return 0.0

    except ValueError as e:
        # This can happen if one of the texts is empty after preprocessing
        # or contains no features for TF-IDF.
        print(f"Error during TF-IDF vectorization: {e}")
        return 0.0
        
    # Cosine similarity between the two document vectors
    # tfidf_matrix[0:1] is the vector for text1
    # tfidf_matrix[1:2] is the vector for text2
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    
    return similarity[0][0]


def generate_content_hash(text_content):
    """Generates a SHA-256 hash for the given text content."""
    return hashlib.sha256(text_content.encode('utf-8')).hexdigest()


# --- Optional Advanced Features (Placeholders) ---
def jaccard_similarity(text1, text2):
    """Calculates Jaccard similarity (token-based)."""
    set1 = set(text1.split())
    set2 = set(text2.split())
    if not set1 and not set2:
        return 0.0
    if not set1 or not set2: # one is empty
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0.0

def ngram_analysis(text, n=3):
    """Generates n-grams for a given text."""
    tokens = text.split()
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

# Fuzzy matching could involve libraries like fuzzywuzzy
# def fuzzy_match(text1, text2):
#     from fuzzywuzzy import fuzz
#     return fuzz.ratio(text1, text2) / 100.0


if __name__ == '__main__':
    # Example Usage (for testing purposes)
    sample_text_1 = "This is the first sample document for testing plagiarism detection."
    sample_text_2 = "This is a second sample document, quite similar to the first one for testing."
    sample_text_3 = "A completely different piece of text to ensure low similarity scores."
    empty_text = ""

    print("--- Preprocessing Examples ---")
    processed_1 = preprocess_text(sample_text_1)
    processed_2 = preprocess_text(sample_text_2)
    processed_3 = preprocess_text(sample_text_3)
    processed_empty = preprocess_text(empty_text)

    print(f"Original 1: {sample_text_1}")
    print(f"Processed 1: {processed_1}")
    print(f"Original 2: {sample_text_2}")
    print(f"Processed 2: {processed_2}")
    print(f"Original 3: {sample_text_3}")
    print(f"Processed 3: {processed_3}")
    print(f"Original Empty: '{empty_text}'")
    print(f"Processed Empty: '{processed_empty}'")


    print("\n--- TF-IDF Cosine Similarity Examples ---")
    similarity_1_2 = calculate_similarity(processed_1, processed_2)
    similarity_1_3 = calculate_similarity(processed_1, processed_3)
    similarity_1_empty = calculate_similarity(processed_1, processed_empty)
    similarity_empty_empty = calculate_similarity(processed_empty, processed_empty)

    print(f"Similarity between Doc 1 and Doc 2: {similarity_1_2:.4f}")
    print(f"Similarity between Doc 1 and Doc 3: {similarity_1_3:.4f}")
    print(f"Similarity between Doc 1 and Empty Doc: {similarity_1_empty:.4f}")
    print(f"Similarity between Empty Doc and Empty Doc: {similarity_empty_empty:.4f}")

    print("\n--- Jaccard Similarity Examples ---")
    j_similarity_1_2 = jaccard_similarity(processed_1, processed_2)
    j_similarity_1_3 = jaccard_similarity(processed_1, processed_3)
    print(f"Jaccard Similarity between Doc 1 and Doc 2: {j_similarity_1_2:.4f}")
    print(f"Jaccard Similarity between Doc 1 and Doc 3: {j_similarity_1_3:.4f}")

    print("\n--- N-gram Example ---")
    ngrams_doc1 = ngram_analysis(processed_1, n=3)
    print(f"3-grams for Processed Doc 1 (first 5): {ngrams_doc1[:5]}")

    print("\n--- File Extraction Example ---")
    # Create dummy files for testing
    test_dir = "test_docs"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    txt_file_path = os.path.join(test_dir, "sample.txt")
    with open(txt_file_path, "w") as f:
        f.write("This is a sample text file.\nIt has multiple lines.")

    # Note: Creating .docx and .pdf programmatically for simple tests is complex.
    # Assume these files exist or test with actual files.
    # For now, we'll just show the .txt extraction.
    try:
        extracted_txt = extract_text_from_file(txt_file_path)
        print(f"Extracted from TXT: '{extracted_txt[:50]}...'")
        
        # Example for a non-existent docx to show error handling (if you don't have one)
        # extracted_docx = extract_text_from_file(os.path.join(test_dir, "sample.docx"))
        # print(f"Extracted from DOCX: '{extracted_docx[:50]}...'")

    except Exception as e:
        print(f"Error during file extraction test: {e}")
    
    # Clean up dummy files
    # os.remove(txt_file_path)
    # os.rmdir(test_dir) # only if empty

    print("\n--- Content Hash Example ---")
    hash1 = generate_content_hash(sample_text_1)
    hash2 = generate_content_hash(sample_text_1) # Should be the same
    hash3 = generate_content_hash(sample_text_2)
    print(f"Hash for text 1: {hash1}")
    print(f"Hash for text 1 (again): {hash2}")
    print(f"Hash for text 2: {hash3}")