import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class ApartmentDocumentChunker:
    def __init__(self, max_chunk_size: int = 800, overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
    
    def chunk(self, text: str) -> List[str]:
        if not text or not text.strip():
            logger.warning("Empty document provided to chunker")
            return []
        
        text = text.strip()
        logger.info(f"Chunking apartment document: {len(text)} characters")
        
        sections = self._split_into_sections(text)
        logger.info(f"Split into {len(sections)} natural sections")
        
        chunks = []
        current_chunk = ""
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            candidate = (current_chunk + "\n\n" + section).strip() if current_chunk else section
            
            if len(candidate) <= self.max_chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    overlap_text = self._get_overlap(current_chunk)
                    current_chunk = overlap_text + section if overlap_text else section
                else:
                    if len(section) > self.max_chunk_size:
                        sub_chunks = self._split_large_section(section)
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1] if sub_chunks else ""
                    else:
                        current_chunk = section
        
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Created {len(chunks)} chunks from document")
        for i, chunk in enumerate(chunks):
            logger.debug(f"Chunk {i+1}: {len(chunk)} chars - '{chunk[:80]}...'")
        
        return chunks
    
    def _split_into_sections(self, text: str) -> List[str]:
        sections = re.split(r'\n\s*\n+', text)
        
        refined_sections = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            if self._has_list_items(section):
                list_items = self._split_list_items(section)
                refined_sections.extend(list_items)
            else:
                refined_sections.append(section)
        
        return refined_sections
    
    def _has_list_items(self, text: str) -> bool:
        lines = text.split('\n')
        if len(lines) < 2:
            return False
        
        list_patterns = [
            r'^\s*[-•*]\s+',
            r'^\s*\d+\.\s+',
            r'^\s*[a-zA-Z]\)\s+',
        ]
        
        list_count = sum(
            1 for line in lines
            if any(re.match(pattern, line) for pattern in list_patterns)
        )
        
        return list_count >= 2
    
    def _split_list_items(self, text: str) -> List[str]:
        list_pattern = r'^\s*(?:[-•*]|\d+\.|[a-zA-Z]\))\s+'
        lines = text.split('\n')
        
        chunks = []
        current = []
        
        for line in lines:
            if re.match(list_pattern, line):
                if current:
                    chunks.append('\n'.join(current))
                    current = []
                current.append(line)
            else:
                if line.strip():
                    if current:
                        current.append(line)
                    else:
                        chunks.append(line)
        
        if current:
            chunks.append('\n'.join(current))
        
        return chunks
    
    def _split_large_section(self, section: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', section)
        
        chunks = []
        current = ""
        
        for sentence in sentences:
            candidate = (current + " " + sentence).strip() if current else sentence
            
            if len(candidate) <= self.max_chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                    overlap_text = self._get_overlap(current)
                    current = overlap_text + sentence if overlap_text else sentence
                else:
                    chunks.append(sentence)
                    current = ""
        
        if current:
            chunks.append(current)
        
        return chunks
    
    def _get_overlap(self, text: str) -> str:
        if len(text) <= self.overlap:
            return text
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if not sentences:
            return text[-self.overlap:]
        
        overlap = ""
        for sentence in reversed(sentences):
            candidate = (sentence + " " + overlap).strip() if overlap else sentence
            if len(candidate) <= self.overlap:
                overlap = candidate
            else:
                break
        
        return overlap if overlap else text[-self.overlap:]


document_chunker = ApartmentDocumentChunker()

