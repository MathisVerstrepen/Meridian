<img src="docs/imgs/readme_header.png" alt="header" />

# Meridian - Graph-Powered Conversational AI

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Frontend](https://img.shields.io/badge/Frontend-Nuxt3-00DC82?logo=nuxt.js&logoColor=white)](https://nuxt.com/)
[![Backend](https://img.shields.io/badge/Backend-Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Actively%20Developed-brightgreen)](https://github.com/your-username/your-repo-name/commits/main)

> [!WARNING]  
> **This project is in its early stages of development.**

## ✨ Introduction

Welcome to Meridian! Built on a **graph-based architecture**, Meridian goes beyond simple turn-taking, enabling richer, more nuanced, and highly efficient interactions.

Traditional AI chats often struggle with complex queries, requiring multiple back-and-forth interactions to gather information. Our innovative approach, deeply rooted in a dynamic graph structure, allows for **intelligent parallelization** of information gathering and processing. Imagine asking a question, and instead of a linear response, our system simultaneously consults multiple specialized AI models, synthesizing their insights into a coherent, comprehensive, and accurate answer.

This isn't just about speed; it's about depth, accuracy, and unlocking advanced AI workflows previously out of reach for consumer applications.

## 🌟 Key Features

* **Graph-Based AI Engine:** At its core, Meridian leverages a sophisticated graph database to represent and process information. This allows for complex relationships between concepts, enabling more intelligent context retention and dynamic query planning.
* **Parallel Query Processing:** User prompts can be dispatched to multiple LLMs in parallel. Their responses are then intelligently combined by a final LLM, delivering a unified and comprehensive answer.
* **Model Agnostic:** Powered by [OpenRouter](https://openrouter.ai/), Meridian seamlessly integrates with various AI models, giving you the flexibility to select the optimal model for each scenario.
* **Oauth & UserPass:** Secure user authentication and management, ensuring that your data is protected and accessible only to you.
* **Attachment Support:** Users can upload attachments, enhancing the context and richness of conversations.
* **Syntax Highlighting:** Code snippets are displayed with syntax highlighting, making it easier to read and understand technical content.
* **LaTeX Rendering:** Mathematical expressions are rendered beautifully, allowing for clear communication of complex ideas.
* **Chat Branching:** Using the graph structure, Meridian supports branching conversations, enabling users to explore different paths and topics without losing context.
* **Highly Customizable:** Meridian is highly configurable, allowing you to tailor the system to your specific needs and preferences.

> See a detailed overview of the features in the [Features.md](docs/Features.md) file.

## 🛠️ Technologies Used

*   **Frontend:**
    *   [Nuxt 3](https://nuxt.com/)
    *   [Vue 3](https://vuejs.org/)
    *   [Tailwind CSS](https://tailwindcss.com/)
*   **Backend:**
    *   [Python](https://www.python.org/)
    *   [FastAPI](https://fastapi.tiangolo.com/)
    *   [Neo4j](https://neo4j.com/)

## 🚀 Running Meridian

### Prerequisites

*   Docker and Docker Compose installed on your machine.
*   [Yq (from Mike Farah)](https://github.com/mikefarah/yq/#install) for YAML processing.

### Local Development Setup

TODO

## 📄 API Documentation

The backend API documentation (powered by FastAPI's Swagger UI) will be available at:
`http://localhost:8000/docs` (when the backend is running).

## 🗺️ Project Structure

```
TODO
```

## 🤝 Contributing

We welcome contributions to Meridian! Whether it's adding new features, improving existing ones, or fixing bugs, your help is appreciated.

## 🐛 Issues and Bug Reports

Found a bug or have a feature request? Please open an issue on our [GitHub Issues page](https://github.com/MathisVerstrepen/Meridian/issues).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Made with ❤️ by Mathis Verstrepen