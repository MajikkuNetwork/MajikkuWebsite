# 1. Use a lightweight version of Python
FROM python:3.9-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your app code
COPY . .

# 5. Tell Docker we are using port 5000
EXPOSE 5000

# 6. The command to run your app
CMD ["python", "app.py"]