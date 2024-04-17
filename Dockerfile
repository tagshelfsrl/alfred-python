FROM python:3.8-slim

# Setup argument for private python repository
ARG PYPI_USER
ARG PYPI_PASS
ARG PYPI_URL=https://${PYPI_USER}:${PYPI_PASS}@pypi.tagshelf.io/simple

# Set working directory
WORKDIR /worker

# Update python deps
RUN pip install -U pip wheel

# Copy requirements
COPY requirements.txt /worker/

# Install deps
RUN pip install -r requirements.txt --extra-index-url="${PYPI_URL}" --no-cache-dir

# Copy directory
COPY ./app /worker/app

# Copy executable files
COPY run.py /worker/

# Set entrypoint
ENTRYPOINT ["python"]

# Set default starting command
CMD ["run.py"]