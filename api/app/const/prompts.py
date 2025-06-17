GLOBAL_SYSTEM_PROMPT = """When you need to write LaTeX, use the following format:  
- For **inline math**: ' $...$ ' (include a space before the opening '$', and a space after the closing '$')  
- For **block math**: ' $$...$$ ' (include a space before the opening '$$', and a space after the closing '$$')  

Where '...' represents your LaTeX code.  

**Key Requirements:**  
1- A space **must** appear immediately before the opening '$' (or '$$')  
2- A space **must** appear immediately after the closing '$' (or '$$')  

**Examples:**  
- Correct inline: ' The formula is ( $E=mc^2$ ) for relativity.'  
- Correct block: ' Consider: $$ \int_a^b f(x)dx $$ '  
- **Incorrect**: 'Missing($spaces$)' or '$$isolated$$' (no surrounding spaces)"""

PARALLELIZATION_AGGREGATOR_PROMPT = """You have been provided with a set of responses from various open-source models to the latest user query. 
Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information 
provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the 
given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, 
coherent, and adheres to the highest standards of accuracy and reliability."""
