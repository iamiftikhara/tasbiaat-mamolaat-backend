from app import create_app

app = create_app()

# This is for Vercel serverless functions
handler = app