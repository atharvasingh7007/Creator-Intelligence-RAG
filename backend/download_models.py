import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def predownload_models():
    """
    Downloads and caches all heavy Machine Learning models required for the RAG platform.
    Run this script during Docker build or deployment setup to prevent end-user wait times.
    """
    logger.info("Starting model pre-download process...")
    start_time = time.time()
    
    # 1. Download Embedding Model
    logger.info("Downloading Embeddings Model (BAAI/bge-small-en-v1.5)...")
    from app.services.embedder import get_embedding_model
    get_embedding_model()
    logger.info("Embeddings Model downloaded and cached successfully.")
    
    # 2. Download Reranker Model
    logger.info("Downloading Reranker Model (BAAI/bge-reranker-v2-m3)...")
    from app.services.reranker import get_reranker
    get_reranker()
    logger.info("Reranker Model downloaded and cached successfully.")

    elapsed = time.time() - start_time
    logger.info(f"All models successfully downloaded in {elapsed:.2f} seconds!")
    logger.info("Deployment is now ready for instant instant user responses.")

if __name__ == "__main__":
    predownload_models()
