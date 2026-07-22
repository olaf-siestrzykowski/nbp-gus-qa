FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model so startup is instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .

RUN chmod +x start.sh

EXPOSE 7860

CMD ["./start.sh"]
