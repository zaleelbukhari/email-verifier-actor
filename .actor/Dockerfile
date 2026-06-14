# Use Apify's optimized Python base image
FROM apify/actor-python:3.11

# Copy requirements first for Docker layer caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./

# Run the Actor as a Python module
CMD ["python3", "-m", "src"]
