#!/usr/bin/env python3
"""
KB Embedding v4.0 - INTELLIGENT CHUNKING
Better document processing, metadata extraction, and semantic chunking
"""

import os
import chromadb
from pathlib import Path
import logging
import hashlib
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IntelligentChunker:
    """Smart document chunking that preserves context"""
    
    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_by_sections(self, text: str, source: str) -> list:
        """Chunk by markdown sections while preserving headers"""
        chunks = []
        
        # Split by level 2-4 headers (## ### ####)
        sections = re.split(r'\n(#{2,4}\s+[^\n]+)\n', text)
        
        current_h1 = ""
        current_h2 = ""
        
        # Extract H1 if exists
        h1_match = re.match(r'#\s+([^\n]+)', text)
        if h1_match:
            current_h1 = h1_match.group(1).strip()
        
        i = 0
        while i < len(sections):
            # Check if this is a header
            if i > 0 and sections[i].startswith('#'):
                header = sections[i]
                content = sections[i + 1] if i + 1 < len(sections) else ""
                
                # Update context headers
                if header.startswith('##') and not header.startswith('###'):
                    current_h2 = header.replace('#', '').strip()
                
                # Build chunk with context
                chunk_text = f"{header}\n{content}"
                
                # Add parent context if available
                context_prefix = ""
                if current_h1:
                    context_prefix = f"# {current_h1}\n"
                if current_h2 and not header.startswith('##'):
                    context_prefix += f"## {current_h2}\n"
                
                full_chunk = context_prefix + chunk_text
                
                # If chunk too large, split it
                if len(full_chunk) > self.chunk_size:
                    sub_chunks = self._split_large_chunk(full_chunk, header)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append({
                        'content': full_chunk.strip(),
                        'source': source,
                        'section': header.strip('#').strip()
                    })
                
                i += 2
            else:
                i += 1
        
        return chunks if chunks else [{'content': text[:self.chunk_size], 'source': source, 'section': 'main'}]
    
    def _split_large_chunk(self, text: str, header: str) -> list:
        """Split large chunks by paragraphs"""
        chunks = []
        paragraphs = text.split('\n\n')
        
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < self.chunk_size:
                current += para + "\n\n"
            else:
                if current:
                    chunks.append({
                        'content': current.strip(),
                        'section': header.strip('#').strip()
                    })
                current = para + "\n\n"
        
        if current:
            chunks.append({
                'content': current.strip(),
                'section': header.strip('#').strip()
            })
        
        return chunks if chunks else [{'content': text[:self.chunk_size], 'section': 'main'}]


class EnhancedMetadataExtractor:
    """Extract rich metadata from documents"""
    
    @staticmethod
    def extract_metadata(text: str, source_file: str) -> dict:
        """Extract all relevant metadata"""
        meta = {
            'file': source_file,
            'doc_type': 'unknown',
            'timestamp': datetime.now().isoformat()
        }
        
        # Detect document type
        if 'contact' in source_file.lower():
            meta['doc_type'] = 'contacts'
        elif 'runbook' in source_file.lower():
            meta['doc_type'] = 'runbooks'
        elif 'incident' in source_file.lower():
            meta['doc_type'] = 'incidents'
        elif 'server' in source_file.lower():
            meta['doc_type'] = 'servers'
        
        # Extract contact info (if exists in chunk)
        name_match = re.search(r'####\s+([^-\n]+?)\s*-\s*([^\n]+)', text)
        if name_match:
            meta['contact_name'] = name_match.group(1).strip()
            meta['contact_role'] = name_match.group(2).strip()
        
        # Extract email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        if email_match:
            meta['contact_email'] = email_match.group(1)
        
        # Extract system references
        systems = []
        for system in ['Server_A', 'Server_B', 'Server_C']:
            if system in text:
                systems.append(system)
        if systems:
            meta['systems'] = ','.join(systems)
        
        # Extract severity
        if any(word in text for word in ['CRITICAL', 'P1', 'Critical']):
            meta['severity'] = 'CRITICAL'
        elif any(word in text for word in ['ERROR', 'P2', 'High']):
            meta['severity'] = 'HIGH'
        elif any(word in text for word in ['WARNING', 'P3', 'Medium']):
            meta['severity'] = 'MEDIUM'
        
        # Extract incident IDs
        incidents = re.findall(r'#\d{4}-\d{4}', text)
        if incidents:
            meta['related_incidents'] = ','.join(list(set(incidents))[:5])
        
        # Extract owner for runbooks
        owner_match = re.search(r'\*\*Owner\*\*:\s*([^\n(]+)', text)
        if owner_match:
            meta['owner'] = owner_match.group(1).strip()
        
        return meta


class KnowledgeBaseBuilder:
    """Build optimized KB"""
    
    def __init__(self, db_path: str = "./chroma_db"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        self.chunker = IntelligentChunker(chunk_size=800, overlap=100)
        self.extractor = EnhancedMetadataExtractor()
        logger.info(f"✅ ChromaDB initialized: {db_path}")
    
    def create_collection(self, name: str):
        """Create fresh collection"""
        try:
            self.client.delete_collection(name)
            logger.info(f"🗑️ Deleted old collection: {name}")
        except:
            pass
        
        collection = self.client.create_collection(
            name=name,
            metadata={"description": "Optimized KB with intelligent chunking", "version": "4.0"}
        )
        logger.info(f"✅ Created collection: {name}")
        return collection
    
    def load_and_embed(self, knowledge_dir: str, collection_name: str = "company_knowledge"):
        """Load and embed documents"""
        
        collection = self.create_collection(collection_name)
        
        kb_path = Path(knowledge_dir)
        if not kb_path.exists():
            logger.error(f"❌ Directory not found: {knowledge_dir}")
            return False
        
        md_files = list(kb_path.glob("*.md"))
        if not md_files:
            logger.error(f"❌ No .md files in {knowledge_dir}")
            return False
        
        logger.info(f"📚 Found {len(md_files)} files")
        
        all_docs = []
        all_metas = []
        all_ids = []
        doc_id = 0
        
        for md_file in md_files:
            logger.info(f"  Processing: {md_file.name}")
            
            try:
                content = md_file.read_text(encoding='utf-8')
                
                # Chunk intelligently
                chunks = self.chunker.chunk_by_sections(content, str(md_file))
                
                for chunk in chunks:
                    # Extract metadata
                    metadata = self.extractor.extract_metadata(chunk['content'], md_file.name)
                    metadata['source'] = chunk.get('source', str(md_file))
                    metadata['section'] = chunk.get('section', 'main')
                    
                    # Clean metadata (ChromaDB requirement)
                    clean_meta = {}
                    for k, v in metadata.items():
                        if v is None or v == "":
                            continue
                        clean_meta[k] = str(v)
                    
                    all_docs.append(chunk['content'])
                    all_metas.append(clean_meta)
                    all_ids.append(f"doc_{doc_id}")
                    doc_id += 1
                
                logger.info(f"    ✓ {len(chunks)} chunks")
            
            except Exception as e:
                logger.error(f"    ❌ Error: {e}")
                continue
        
        # Embed in batches
        logger.info(f"\n🚀 Embedding {len(all_docs)} chunks...")
        batch_size = 100
        
        for i in range(0, len(all_docs), batch_size):
            batch_docs = all_docs[i:i+batch_size]
            batch_metas = all_metas[i:i+batch_size]
            batch_ids = all_ids[i:i+batch_size]
            
            try:
                collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids
                )
                logger.info(f"  ✓ Batch {i//batch_size + 1}: {min(i+batch_size, len(all_docs))}/{len(all_docs)}")
            except Exception as e:
                logger.error(f"  ❌ Batch failed: {e}")
        
        final_count = collection.count()
        logger.info(f"✅ Embedded {final_count} documents")
        
        # Test queries
        self.test_collection(collection)
        
        return True
    
    def test_collection(self, collection):
        """Test with realistic queries"""
        logger.info("\n🧪 Testing collection...")
        
        tests = [
            ("database connection pool Server_A", "Should find Sarah Chen + connection pool runbook"),
            ("memory leak critical", "Should find Lisa Park + memory leak runbook"),
            ("payment timeout error", "Should find Mike Rodriguez + payment runbook"),
            ("disk space full", "Should find Tom Bradley + disk space runbook"),
            ("security incident CVE", "Should find James Wilson + security runbook")
        ]
        
        for query, expected in tests:
            results = collection.query(
                query_texts=[query],
                n_results=3,
                include=["documents", "metadatas", "distances"]
            )
            
            if results['documents'] and results['documents'][0]:
                doc = results['documents'][0][0]
                meta = results['metadatas'][0][0]
                dist = results['distances'][0][0] if 'distances' in results else 0
                
                contact = meta.get('contact_name', 'N/A')
                doc_type = meta.get('doc_type', 'unknown')
                
                logger.info(f"  ✓ '{query}'")
                logger.info(f"      → Type: {doc_type}, Contact: {contact}, Distance: {dist:.3f}")
            else:
                logger.warning(f"  ⚠️ '{query}' → No results")


def main():
    logger.info("="*60)
    logger.info("KB Embedding v4.0 - INTELLIGENT CHUNKING")
    logger.info("="*60)
    
    knowledge_dir = "./knowledge_base"
    db_path = "./chroma_db"
    
    # Check if knowledge_base exists
    if not Path(knowledge_dir).exists():
        logger.error(f"❌ Directory not found: {knowledge_dir}")
        logger.info("💡 Creating knowledge_base directory...")
        Path(knowledge_dir).mkdir(exist_ok=True)
        logger.info("   Place your .md files in ./knowledge_base/")
        return False
    
    builder = KnowledgeBaseBuilder(db_path=db_path)
    success = builder.load_and_embed(knowledge_dir)
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("✅ SUCCESS! Knowledge base ready")
        logger.info(f"   Location: {db_path}")
        logger.info(f"   Intelligent chunking + metadata extraction")
        logger.info("="*60)
    else:
        logger.error("\n❌ Embedding failed - check logs above")
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)