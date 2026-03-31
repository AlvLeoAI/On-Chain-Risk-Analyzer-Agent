import asyncio
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.models import DocumentEmbedding

try:
    from google import genai
except ImportError:  # pragma: no cover - depends on local environment
    genai = None

logger = logging.getLogger(__name__)


def _get_client():
    if genai is None:
        raise RuntimeError("google-genai is not installed")
    return genai.Client()

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Splits a large document into smaller chunks for embedding.
    Uses simple character-based chunking with overlap to preserve context.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Advance by chunk_size - overlap
        start += (chunk_size - overlap)
        if start >= text_length:
            break
            
    return chunks

# Semaphore to limit concurrent embedding generation calls (prevents rate limits/hangs)
EMBED_SEMAPHORE = asyncio.Semaphore(10)

async def get_embedding(content: str) -> List[float]:
    """
    Generates a 768-dimensional vector embedding for a given string using Gemini's embedding model.
    """
    async with EMBED_SEMAPHORE:
        try:
            client = _get_client()
            # Use the async client (aio) to prevent blocking the event loop
            response = await client.aio.models.embed_content(
                model="text-embedding-004",
                contents=content
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

async def ingest_document_to_db(db: AsyncSession, project_id: str, document_text: str) -> None:
    """
    Chunks a document, generates embeddings in parallel, and saves them to the database.
    """
    logger.info(f"Ingesting document for project {project_id} into database...")
    chunks = chunk_text(document_text)
    
    # Generate embeddings in parallel for all chunks
    # Note: For extremely large docs (e.g., 500+ chunks), we might want to batch this 
    # to avoid rate limits, but for standard whitepapers, parallel is fine.
    tasks = [get_embedding(chunk) for chunk in chunks]
    vectors = await asyncio.gather(*tasks)
    
    new_embeddings = []
    for chunk, vector in zip(chunks, vectors):
        if vector:
            embedding_obj = DocumentEmbedding(
                project_id=project_id,
                content=chunk,
                embedding=vector
            )
            new_embeddings.append(embedding_obj)
            
    if new_embeddings:
        db.add_all(new_embeddings)
        await db.commit()
        logger.info(f"Successfully ingested {len(new_embeddings)} chunks for project {project_id}.")
    else:
        logger.warning(f"No chunks were generated for project {project_id}.")

async def retrieve_relevant_chunks_from_db(db: AsyncSession, project_id: str, query: str, top_k: int = 5) -> str:
    """
    Performs a vector similarity search in the database for the given query and project.
    Returns a concatenated string of the most relevant chunks.
    """
    query_vector = await get_embedding(query)
    if not query_vector:
        return ""
        
    vector_str = f"[{','.join(map(str, query_vector))}]"
    
    stmt = text("""
        SELECT content
        FROM document_embeddings
        WHERE project_id = :project_id
        ORDER BY embedding <=> :vector_str
        LIMIT :top_k
    """)
    
    try:
        result = await db.execute(stmt, {
            "project_id": project_id,
            "vector_str": vector_str,
            "top_k": top_k
        })
        
        relevant_chunks = [row[0] for row in result.fetchall()]
        
        if not relevant_chunks:
            logger.info(f"No relevant chunks found for query in project {project_id}.")
            return ""
            
        logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks for project {project_id}.")
        return "\n\n---\n\n".join(relevant_chunks)
        
    except Exception as e:
        logger.error(f"Error during vector retrieval: {e}")
        return ""

