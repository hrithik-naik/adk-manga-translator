# 🈺 ADK Manga Translator

A multi-agent, multimodal pipeline built using Google's **Agent Development Kit (ADK)** to translate Japanese manga panels into English. This system is modular, autonomous, and capable of handling the full pipeline from image preprocessing to final language translation and proofreading.

---

## 🧠 Project Overview

**ADK Manga Translator** is a workflow of intelligent agents designed to:
- Clean and preprocess manga panels.
- Perform high-quality Japanese-to-English translation.
- Proofread and refine the output iteratively.

This setup uses a **manager agent** to orchestrate all the sub-agents in a structured pipeline using `SequentialAgent` and `LoopAgent` abstractions.

---

## 🕹️ Agent Architecture

### 1. **`manager`** (Root Agent)
- **Type**: `Agent`
- **Model**: `gemini-2.0-flash`
- **Responsibility**: Oversees and delegates tasks across all sub-agents.
- **Sub-agents**: `workflow` (the full translation pipeline)
- **Tools**: Has access to `proof_reader` as a fallback tool.

---

### 2. **`workflow`** (Sequential Pipeline)
- **Type**: `SequentialAgent`
- **Responsibility**: Executes the following steps in order:
    1. `manga_cleaner` – cleans image artifacts and prepares panel.
    2. `refinement_loop` – runs translator inside a 1-pass loop to ensure translation meets quality.
    3. `proof_reader` – polishes the translated text.

---

### 3. **`refinement_loop`**
- **Type**: `LoopAgent`
- **Responsibility**: Uses `translator` to perform a refinement pass.
- **Max Iterations**: 1 (can be extended later for iterative QA)

---

### 4. **Sub-Agents**
- **`manga_cleaner`**: Image preprocessing and artifact removal.
- **`translator`**: Converts Japanese text to English.
- **`proof_reader`**: Ensures fluent, natural translation and grammar consistency.

---

## 🚀 How It Works

### 🔗 Input Format
