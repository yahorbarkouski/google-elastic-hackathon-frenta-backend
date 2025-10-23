import asyncio
import logging

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class EnrichmentService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.flash_model = genai.GenerativeModel("gemini-2.5-pro")
    
    async def generate_property_summary(
        self, 
        description: str, 
        image_descriptions: list[str]
    ) -> str:
        prompt = self._build_property_summary_prompt(description, image_descriptions)
        
        try:
            response = await asyncio.to_thread(
                self.flash_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    candidate_count=1
                )
            )
            
            summary = response.text.strip()
            summary = self._clean_summary(summary)
            logger.info(f"Generated property summary: {len(summary)} chars")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating property summary: {e}")
            return ""
    
    def _build_property_summary_prompt(
        self, 
        description: str, 
        image_descriptions: list[str]
    ) -> str:
        image_context = ""
        if image_descriptions:
            image_context = "\n\nImage descriptions:\n" + "\n".join(
                f"{i+1}. {desc}" for i, desc in enumerate(image_descriptions) if desc
            )
        
        return f"""Write a luxury property summary. Return ONLY the summary text, no preamble or meta-commentary.

Style requirements:
- Luxury hospitality tone (sophisticated, inviting, aspirational)
- 3-5 sentences, 150-250 words
- Evocative language emphasizing experience and lifestyle
- Flow like a boutique hotel description

Example output format (DO NOT include phrases like "Here is" or "Of course"):
"Wander Joshua Tree Solace is a secluded desert oasis offering an unparalleled escape in the heart of the California high desert. This luxurious retreat provides breathtaking desert views, allowing guests to fully immerse themselves in the stunning natural landscape. Spend your days lounging by the refreshing outdoor pool, soaking up the sun and enjoying the tranquility of the surroundings."

Property details:
{description}
{image_context}

Return ONLY the property summary, starting immediately with the description:"""
    
    def _clean_summary(self, summary: str) -> str:
        unwanted_prefixes = [
            "of course.",
            "here is",
            "here's",
            "certainly.",
            "sure.",
            "absolutely.",
            "i'd be happy to",
            "let me",
        ]
        
        lines = summary.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            is_meta = False
            for prefix in unwanted_prefixes:
                if line_lower.startswith(prefix):
                    is_meta = True
                    break
            
            if "summary" in line_lower and ":" in line:
                is_meta = True
            
            if not is_meta and line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def generate_location_summary(
        self,
        location: dict[str, float],
        address: str
    ) -> tuple[str, str | None]:
        from app.services.grounding import grounding_service
        
        try:
            summary, widget_token = await grounding_service.generate_location_description(
                location=location,
                address=address
            )
            
            summary = self._clean_summary(summary)
            logger.info(f"Generated location summary: {len(summary)} chars")
            return summary, widget_token
            
        except Exception as e:
            logger.error(f"Error generating location summary: {e}")
            return "", None
    
    async def generate_title(self, description: str, address: str = None) -> str:
        prompt = f"""Generate a short, compelling property title (5-8 words maximum) for this apartment.

Property description:
{description}

{f'Address: {address}' if address else ''}

Style:
- Professional and descriptive
- Include key feature (e.g., "Loft", "Penthouse", "Studio")
- Include location if notable (e.g., "Williamsburg", "SoHo")
- Examples: "Stunning Williamsburg Loft", "Modern SoHo Penthouse", "Bright Studio in Chelsea"

Return ONLY the title, nothing else:"""
        
        try:
            response = await asyncio.to_thread(
                self.flash_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=20
                )
            )
            
            title = response.text.strip().strip('"').strip("'")
            logger.info(f"Generated title: {title}")
            return title
            
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            return ""


enrichment_service = EnrichmentService()

