# Hybrid AI Agent

A lightweight Python agent that routes user input between deterministic math execution, LLM fallback, and tool-based search.

## What it does

This project combines rule-based logic with an LLM to handle different kinds of user input through different paths:

- Calculator path for supported math queries  
- LLM fallback for unusual or poorly phrased math  
- Search tool path for factual or definition-style questions  
- Direct LLM response for casual conversation  

## Why this project exists

The goal was to build a small but real agent system rather than a simple chatbot.

Instead of sending every query directly to the language model, the program first decides whether the request can be handled more reliably with deterministic logic.

## Architecture

1. Calculator (deterministic)
   - Detects math-like input
   - Parses natural-language math phrases
   - Evaluates safely using Python AST

2. Calculator → LLM fallback
   - If parsing fails, falls back to LLM

3. LLM → Search Tool
   - LLM chooses search for factual queries

4. Direct LLM Response
   - Handles casual input

## Example execution paths

Calculator success:
[CALCULATOR] what is five times 7 -> 5 * 7 -> 35

Calculator failed → LLM:
[CALCULATOR FAILED → LLM] what is plus of five and three -> + of 5 and 3

LLM route to search:
[LLM] what is israel
[SEARCH] israel

Direct LLM response:
[LLM] hello

## Project structure

- main.py
- agent.py
- tools.py
- math_utils.py

## Tech used

- Python
- OpenAI API
- python-dotenv
- requests
- word2number

## Setup

1. Create virtual environment
2. Install dependencies: pip install -r requirements.txt
3. Add .env file with OPENAI_API_KEY

## Run

py main.py
