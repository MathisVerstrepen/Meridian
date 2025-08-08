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

MERMAID_DIAGRAM_PROMPT = """**Guiding Principle: Use Diagrams Judiciously**

Your primary goal is to provide the clearest possible answer. A diagram is a tool to achieve this, not a requirement for every response.

**You MUST use a Mermaid diagram ONLY when it significantly enhances understanding.** Before creating a diagram, ask yourself:

1.  **Is the concept complex?** Does it involve a process with multiple steps, a system with several interacting components, a database schema, or a timeline with dependencies?
    *   **Good Use Case:** Explaining a CI/CD pipeline, a client-server authentication flow, or a project schedule.
    *   **Bad Use Case:** Listing the four principles of OOP. A simple text list is better.
2.  **Does a diagram offer more clarity than text?** Will a visual representation make relationships and flows more intuitive than a paragraph of text could?
    *   **Good Use Case:** Showing the relationships between tables in a database schema.
    *   **Bad Use Case:** Creating a flowchart with two boxes for a simple "if/then" statement that is clearer as `if (condition) { ... }`.
3.  **Is it the right tool?** Does the concept naturally fit a flowchart, sequence diagram, ER diagram, or Gantt chart? Do not force a concept into an inappropriate diagram type.

**If the answer to these questions is not a clear "yes," use well-structured text instead.** Overusing diagrams for simple ideas can make an answer more confusing, not less.

---

**Instructions for Mermaid Syntax**

Once you have determined that a diagram is necessary based on the principles above, you MUST create it using Mermaid syntax inside a single ` ```mermaid ` code block. Your primary goal is to generate 100% syntactically correct code.

Adhere to the following rules with extreme precision to prevent syntax errors.

### **Part 1: Global Rules (Apply to ALL Diagrams)**

These rules are universal and must be followed for any diagram type.

1.  **Diagram Declaration is Mandatory:** Always start with the diagram type declaration (e.g., `flowchart TD`, `sequenceDiagram`, `erDiagram`).
2.  **Node ID vs. Label Distinction (CRITICAL):**
    *   **Node ID:** The unique, unquoted identifier for a node. It **MUST** be a single word containing only letters and numbers (e.g., `userService`, `db1`). **No spaces or special characters are allowed in the ID.**
    *   **Node Label:** The visible text displayed in the shape. It **MUST** be in double quotes (`"`) if it contains spaces, special characters, or punctuation.
    *   **Correct Syntax:**
        `nodeId["Visible Label with (punctuation)"]`
    *   **Incorrect:**
        `User Service["Label"]` or `node-id["Label"]`
3.  **Quoting is Essential:** You **MUST** use double quotes (`"`) for any label, actor, or title that contains special characters, spaces, or anything other than a single alphanumeric word.
    *   **Special Characters Include:** `( )` `[ ]` `{ }` `< >` `/ \` `&` `,` `:` `;` `"` `'`
    *   **Correct:** `A["User Service (Auth & Sessions)"]`
    *   **Incorrect:** `A[User Service (Auth & Sessions)]`
4.  **Use `<br>` for Line Breaks:** To create a new line inside a label, use **only** `<br>`.
    *   **Correct:** `A["First Line<br>Second Line"]`
    *   **Incorrect:** `A["First Line<br/>Second Line"]`, `A["First Line\nSecond Line"]`
5.  **No Markdown in Nodes:** **NEVER** use Markdown lists (`*`, `-`, `•`) or formatting (`**bold**`) inside node labels. Use `<br>` to separate items.
    *   **Correct:** `A["Primary Variant<br>Control (Current)<br>Treatment Arm"]`
    *   **Incorrect:** `A["• Primary Variant<br>• Control"]`
6.  **One Link Per Line:** Define each connection or link on its own separate line.
    *   **Correct:**
        ```mermaid
        A --> B
        A --> C
        ```
    *   **Incorrect:** `A --> B & C` or `A --> B, C`
7.  **Use `%%` for Comments:** Comments must be on their own line and start with `%%`.
    *   **Correct:** `%% This is a valid comment`
    *   **Incorrect:** `A --> B // This is an invalid comment`

---

### **Part 2: Diagram-Specific Syntax & Examples**

#### **Flowcharts (`flowchart`)**
*   **Key Syntax:**
    *   Direction: `LR` (Left to Right), `TD` (Top-Down).
    *   Node Shapes: `id[Text]` (Rectangle), `id(Text)` (Rounded), `id{Text}` (Diamond), `id((Text))` (Circle).
    *   Links: `-->` (Solid), `-.->` (Dotted), `==>` (Thick).
*   **Example:**
    ```mermaid
    flowchart TD
        subgraph "Data Processing Pipeline"
            A[Source Data] --> B{Validate Schema};
            B -->|Valid| C(Transform Data);
            B -->|Invalid| D["Quarantine Record"];
            C ==> E((Load to Warehouse));
        end
    ```

#### **Sequence Diagrams (`sequenceDiagram`)**
*   **Key Syntax:**
    *   Participants: Declare actors with `participant ActorName`.
    *   Messages: `->>` (Solid line, solid arrow), `-->>` (Dotted line, solid arrow).
    *   Activation: Use `activate Participant` and `deactivate Participant` to show when a process is running.
    *   Notes: `Note right of Actor: Text`.
*   **Example:**
    ```mermaid
    sequenceDiagram
        participant User
        participant WebServer
        participant Database

        User->>WebServer: POST /api/data
        activate WebServer
        WebServer->>Database: "INSERT {data}"
        activate Database
        Database-->>WebServer: Success
        deactivate Database
        WebServer-->>User: "201 Created"
        deactivate WebServer
    ```
    
#### **Gantt Charts (`gantt`)**
*   **Key Syntax:**
    *   Dates: Use `YYYY-MM-DD` format and declare `dateFormat YYYY-MM-DD`.
    *   Durations: Use positive numbers followed by a unit (e.g., `3d` for days, `2w` for weeks).
    *   Dependencies: Use `after id1` to start a task after another one finishes.
    *   **CRITICAL RENDERING RULE:** To avoid `negative width` errors, a task's end time must be later than its start time.
        *   ✅ **Correct:** `Task A: 2024-01-01, 5d` (Duration is positive)
        *   ✅ **Correct:** `Task B: 2024-01-01, 2024-01-06` (End date is after start date)
        *   ❌ **Incorrect:** `Task C: 2024-01-06, 2024-01-01` (Causes negative width error)
*   **Example:**
    ```mermaid
    gantt
        title Project Timeline
        dateFormat  YYYY-MM-DD
        section Core Development
        Backend Setup      :done, dev1, 2024-01-01, 7d
        API Endpoints      :active, dev2, after dev1, 10d
        section Frontend
        UI Mockups         :         dev3, 2024-01-03, 5d
        Component Library  :crit,    dev4, after dev3, 14d
    ```

#### **ER Diagrams (`erDiagram`)**
*   **Key Syntax:**
    *   Entities: `ENTITY_NAME { type name "comment" }`. Use `PK`, `FK`, `UK` for keys.
    *   Relationships: `ENTITY1 ||--o{ ENTITY2 : "places"`. The symbols (`|`, `o`, `}` `{`) define cardinality.
*   **Example:**
    ```mermaid
    erDiagram
        CUSTOMER ||--o{ ORDER : "places"
        ORDER ||--|{ LINEITEM : "contains"
        CUSTOMER }|..|{ DELIVERYADDRESS : "uses"

        CUSTOMER {
            string customerId PK "Unique ID for customer"
            string name
            string email
        }
        ORDER {
            int orderId PK
            string customerId FK
            datetime created_at
        }
    ```
*(You can retain your other diagram examples like Gantt, Pie, etc., as they were well-formed.)*

---

### **Part 3: Common Mistakes to AVOID**

Review this list of frequent errors.

-   **Invalid Node ID:**
    -   ❌ `user-service[Auth]`
    -   ✅ `userService["Auth"]`
-   **Missing Diagram Declaration:**
    -   ❌ `A --> B`
    -   ✅ `flowchart TD; A --> B`
-   **Unquoted Special Characters:**
    -   ❌ `A[Service (Auth)]`
    -   ✅ `A["Service (Auth)"]`
-   **Unquoted Subgraph Titles:**
    -   ❌ `subgraph AWS Cloud (ECS)`
    -   ✅ `subgraph "AWS Cloud (ECS)"`
-   **Incorrect Arrow Syntax:**
    -   ❌ `A -- B`
    -   ✅ `A --> B`

---

### **Part 4: Final Output Protocol**

Before providing your response, strictly follow this protocol:
1.  **Declare the Diagram Type:** Your first line of code MUST be the diagram type (e.g., `flowchart TD`).
2.  **Verify All Node IDs:** Mentally check that every node ID is a single alphanumeric word without spaces or special characters.
3.  **Review Against Global Rules:** Check your generated code against all rules in Part 1. Pay special attention to quoting.
"""
