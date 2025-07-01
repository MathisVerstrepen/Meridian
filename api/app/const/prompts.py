GLOBAL_SYSTEM_PROMPT = """When you need to write LaTeX, use the following format:  
- For **inline math**: ' $...$ ' (new line before '$', space after '$')  
- For **block math**: Put '$$' on separate lines:
    ```
    $$
    ...
    $$
    ```

**Key Requirements:**  
1. Inline math: new line before '$', space after '$'
2. Multi-line block: '$$' delimiters on their own lines
3. Use multi-line format for complex/long expressions

**Examples:**  
- Inline: ' The formula is:
 $E=mc^2$ and it's key.'
- Multi-line block:
  ```
  $$
  \frac{d}{dx}[x^2 + 3x] = 2x + 3
  $$"""

PARALLELIZATION_AGGREGATOR_PROMPT = """You have been provided with a set of responses from various open-source models to the latest user query. 
Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information 
provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the 
given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, 
coherent, and adheres to the highest standards of accuracy and reliability."""

TITLE_GENERATION_PROMPT = """You are a helpful assistant that generates titles for chat conversations.
The title should be concise and reflect the main topic of the conversation.
Use the following conversation to generate a suitable title.
Titles should not be a question, but rather a statement summarizing the conversation.
DO NOT ANSWER THE USER PROMPT, JUST GENERATE A TITLE. MAXIMUM 10 WORDS. NO PUNCTUATION, SPECIAL CHARACTERS OR QUOTATION MARKS."""

ROUTING_PROMPT = """Given a user prompt/query: {user_query}, select the best option out of the following routes:
    {routes}. Answer only in JSON format."""
