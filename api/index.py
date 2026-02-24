"""Vercel serverless entry point for FastAPI."""

from legal_chatbot.api.app import create_app

app = create_app()
