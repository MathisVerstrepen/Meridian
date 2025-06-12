export const DEFAULT_NODE_ID = '00000000-0000-0000-0000-000000000000';

export const DEFAULT_SYSTEM_PROMPT = `When you need to write LaTeX, use the following format:  
- For **inline math**: ' $...$ ' (include a space before the opening '$', and a space after the closing '$')  
- For **block math**: ' $$...$$ ' (include a space before the opening '$$', and a space after the closing '$$')  

Where '...' represents your LaTeX code.  

**Key Requirements:**  
1- A space **must** appear immediately before the opening '$' (or '$$')  
2- A space **must** appear immediately after the closing '$' (or '$$')  

**Examples:**  
- Correct inline: ' The formula is ( $E=mc^2$ ) for relativity.'  
- Correct block: ' Consider: $$ \int_a^b f(x)dx $$ '  
- **Incorrect**: 'Missing($spaces$)' or '$$isolated$$' (no surrounding spaces)`;
