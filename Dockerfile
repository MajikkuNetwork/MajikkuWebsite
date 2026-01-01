# Use a lightweight Python version
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port Flask runs on
EXPOSE 5000

# Command to run the app using Gunicorn
# "app:app" means "look in app.py for the object named app"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]